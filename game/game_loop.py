import asyncio

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from database import games
import messages
from .types import GameState, GameStatus, GameSession
from .scoring import finalize_question_scores, show_current_scores
from .partial_display import split_question_into_parts, should_display_partially


async def wait_with_pause(session: GameSession, seconds: float) -> None:
    if not session.pause_event:
        await asyncio.sleep(seconds)
        return
    
    remaining = seconds
    while remaining > 0:
        if not session.pause_event.is_set():
            await session.pause_event.wait()
        
        if session.timer_extension > 0:
            remaining = session.timer_extension
            session.timer_extension = 0.0
        
        sleep_time = min(0.5, remaining)
        await asyncio.sleep(sleep_time)
        
        if session.pause_event.is_set():
            remaining -= sleep_time


async def wait_for_answer_or_timeout(session: GameSession) -> bool:
    if not session.answer_event or not session.pause_event:
        await asyncio.sleep(session.timer_extension)
        session.timer_extension = 0.0
        return False
    
    remaining = 15.0

    total_players = len(session.players)
    if session.spectators:
        total_players = len([p for p in session.players if p not in session.spectators])
    
    while remaining > 0:
        if not session.pause_event.is_set():
            await session.pause_event.wait()
            continue
        
        if session.answer_event.is_set():
            return True
        
        if session.answered_players and len(session.answered_players) >= total_players:
            return True
        
        if session.timer_extension > 0:
            remaining = session.timer_extension
            session.timer_extension = 0.0
        
        sleep_time = min(0.1, remaining)
        await asyncio.sleep(sleep_time)
        remaining -= sleep_time
    
    return False


async def game_loop(session: GameSession, bot: Bot) -> None:
    try:
        themes = session.pack_file.get('themes', [])
        pack_info = session.pack_file.get('info', '')
        
        if pack_info and session.current_theme_idx == 0 and session.current_question_idx == 0:
            try:
                await bot.send_message(
                    session.game_chat_id,
                    messages.msg_pack_info(pack_info),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await wait_with_pause(session, 5)
            
            # Display list of themes that will be played
            theme_names = []
            for theme_idx in session.pack_themes:
                if theme_idx < len(themes):
                    theme_name = themes[theme_idx].get('name', f'Тема {theme_idx + 1}')
                    theme_names.append(theme_name)
            
            if theme_names:
                try:
                    await bot.send_message(
                        session.game_chat_id,
                        messages.msg_themes_list(theme_names),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await wait_with_pause(session, 5)
        
        theme_idx = session.current_theme_idx
        
        while theme_idx < len(session.pack_themes):
            pack_theme_index = session.pack_themes[theme_idx]
            
            if pack_theme_index >= len(themes):
                theme_idx += 1
                continue
            
            theme = themes[pack_theme_index]
            theme_name = theme.get('name', f'Тема {theme_idx + 1}')
            
            session.state = GameState.SHOWING_THEME
            try:
                await bot.send_message(
                    session.game_chat_id,
                    messages.msg_theme_name(theme_name),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await wait_with_pause(session, 7)
            
            questions = theme.get('questions', [])
            question_idx = session.current_question_idx if theme_idx == session.current_theme_idx else 0
            
            while question_idx < len(questions):
                session.state = GameState.SHOWING_QUESTION

                question = questions[question_idx]
                
                await games.set_current_position(session.game_chat_id, theme_idx, question_idx)
                session.current_theme_idx = theme_idx
                session.current_question_idx = question_idx
                
                if theme_idx == len(session.pack_themes) - 1 and question_idx >= len(questions) - 2:
                    await show_current_scores(session, bot)
                    await wait_with_pause(session, 3)
                
                cost = question.get('cost', (question_idx + 1) * 10)
                question_text = question.get('question', '')
                
                short_theme_name = theme.get('name', f'Тема {theme_idx + 1}')
                
                # Create answer keyboard (reply keyboard on phone)
                answer_keyboard = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="+")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                
                # Show "Attention, question!" with the answer keyboard
                try:
                    await bot.send_message(
                        session.game_chat_id,
                        messages.msg_attention_question(),
                        reply_markup=answer_keyboard
                    )
                except Exception:
                    pass
                await wait_with_pause(session, 2)
                
                # Check if question should be displayed in parts
                if session.partial_display_enabled and should_display_partially(question_text):
                    # Split question into parts
                    session.current_question_parts = split_question_into_parts(question_text)
                    session.current_part_index = 0
                    total_parts = len(session.current_question_parts)
                    
                    # Display first part
                    first_part = session.current_question_parts[0]
                    try:
                        question_msg = await bot.send_message(
                            session.game_chat_id,
                            messages.msg_question_partial(cost, short_theme_name, first_part, 1, total_parts),
                            parse_mode="HTML"
                        )
                    except Exception:
                        # If question display fails, skip to next question
                        question_idx += 1
                        continue
                    
                    # Display remaining parts progressively
                    # Each part already contains accumulated text, so just use it directly
                    for part_idx in range(1, total_parts):
                        await wait_with_pause(session, 0.5)  # Wait between parts
                        session.current_part_index = part_idx
                        current_part_text = session.current_question_parts[part_idx]
                        
                        # Edit message to show current accumulated text
                        try:
                            await bot.edit_message_text(
                                chat_id=session.game_chat_id,
                                message_id=question_msg.message_id,
                                text=messages.msg_question_partial(cost, short_theme_name, current_part_text, part_idx + 1, total_parts),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                else:
                    # Display question all at once (normal behavior)
                    session.current_question_parts = None
                    session.current_part_index = 0
                    try:
                        question_msg = await bot.send_message(
                            session.game_chat_id,
                            messages.msg_question(cost, short_theme_name, question_text),
                            parse_mode="HTML"
                        )
                    except Exception:
                        # If question display fails, skip to next question
                        question_idx += 1
                        continue
                
                session.current_question_message_id = question_msg.message_id
                session.current_question_data = {**question, 'theme_name': short_theme_name}
                session.answering_player_id = None
                session.answer_correct = None
                session.answered_players = {}
                session.question_claimed = False
                session.disputed_players = set()
                if session.dispute_poll_id:
                    from .sessions import session_manager
                    session_manager.unregister_poll(session.dispute_poll_id)
                session.dispute_poll_id = None
                session.dispute_player_id = None
                session.dispute_votes = None
                if session.answer_event:
                    session.answer_event.clear()
                
                session.state = GameState.WAITING_ANSWER

                answered = await wait_for_answer_or_timeout(session)
                
                session.state = GameState.SHOWING_ANSWER
                answer_text = question.get('answer', '')
                comment = question.get('comment', '')
                
                # Create score correction keyboard (reply keyboard on phone)
                correction_keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="да"),
                            KeyboardButton(text="нет"),
                            KeyboardButton(text="случ")
                        ]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=False  # Keep visible during correction phase
                )
                
                # Remove keyboard after score correction
                remove_keyboard = ReplyKeyboardRemove()
                
                if session.answered_players:
                    try:
                        await bot.send_message(
                            session.game_chat_id,
                            messages.msg_answer(answer_text, comment),
                            parse_mode="HTML",
                            reply_markup=correction_keyboard
                        )
                    except Exception:
                        # If answer display fails, try without HTML parsing
                        try:
                            await bot.send_message(
                                session.game_chat_id,
                                f"Ответ: {answer_text}",
                                reply_markup=correction_keyboard
                            )
                        except Exception:
                            pass
                else:
                    try:
                        await bot.send_message(
                            session.game_chat_id,
                            messages.msg_answer(answer_text, comment),
                            parse_mode="HTML",
                            reply_markup=remove_keyboard
                        )
                    except Exception:
                        # If answer display fails, try without HTML parsing
                        try:
                            await bot.send_message(
                                session.game_chat_id,
                                f"Ответ: {answer_text}",
                                reply_markup=remove_keyboard
                            )
                        except Exception:
                            pass
                
                if session.answered_players:
                    session.state = GameState.SCORE_CORRECTION
                    await wait_with_pause(session, 10)
                    
                    await finalize_question_scores(session, cost, bot)
                else:
                    await wait_with_pause(session, 5)
                
                question_idx += 1
            
            await show_current_scores(session, bot)
            await wait_with_pause(session, 5)
            
            session.current_question_idx = 0
            theme_idx += 1
        
        session.state = GameState.GAME_OVER
        await bot.send_message(session.game_chat_id, messages.msg_game_over())
        await games.update_game_status(session.game_chat_id, GameStatus.FINISHED)
        
        from .end_game import finalize_game
        await finalize_game(session.game_chat_id, bot)
            
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await bot.send_message(session.game_chat_id, messages.msg_error(str(e)))
        session.state = GameState.IDLE

