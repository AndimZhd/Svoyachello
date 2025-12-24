import asyncio

from aiogram import Bot

from database import games
import messages
from .types import GameState, GameStatus, GameSession
from .scoring import finalize_question_scores, show_current_scores


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
    
    while remaining > 0:
        if not session.pause_event.is_set():
            await session.pause_event.wait()
            continue
        
        if session.answer_event.is_set():
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
            await bot.send_message(
                session.game_chat_id,
                messages.msg_pack_info(pack_info),
                parse_mode="HTML"
            )
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
            await bot.send_message(
                session.game_chat_id,
                messages.msg_theme_name(theme_name),
                parse_mode="HTML"
            )
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
                
                await bot.send_message(session.game_chat_id, messages.msg_attention_question())
                await wait_with_pause(session, 2)
                
                cost = question.get('cost', (question_idx + 1) * 10)
                question_text = question.get('question', '')
                
                short_theme_name = theme.get('name', f'Тема {theme_idx + 1}')
                
                question_msg = await bot.send_message(
                    session.game_chat_id,
                    messages.msg_question(cost, short_theme_name, question_text),
                    parse_mode="HTML"
                )
                
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
                
                await bot.send_message(session.game_chat_id, messages.msg_answer(answer_text, comment), parse_mode="HTML")
                
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

