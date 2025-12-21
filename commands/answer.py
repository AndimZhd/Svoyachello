import asyncio

from aiogram import Bot, Router, types, F
from aiogram.filters import Command

from game import get_session, start_player_answering, submit_answer, cancel_answering, GameState, AnswerState
from messages import (
    msg_time_up,
    msg_player_answering,
    msg_question_hidden,
    msg_question,
    msg_someone_answering,
    msg_correct_answer,
    msg_incorrect_answer,
    msg_question_claimed,
    msg_answer_already_correct,
    msg_answer_confirmed,
    msg_answer_already_incorrect,
    msg_answer_rejected,
    msg_answer_already_accidental,
    msg_answer_marked_accidental,
)

router = Router()

# Track players waiting for answer input
_waiting_for_answer: dict[tuple[int, int], asyncio.Task] = {}  # (chat_id, user_id) -> timeout task


@router.message(Command("answer"))
@router.message(F.text == "+")
async def answer_command(message: types.Message, bot: Bot) -> None:
    """Player wants to answer the current question."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    # Check if there's an active game session
    session = get_session(chat_id)
    if not session:
        return
    
    if session.state != GameState.WAITING_ANSWER:
        if session.state == GameState.PLAYER_ANSWERING:
            await message.answer(msg_someone_answering())
        return
    
    # Start answering mode
    if not start_player_answering(chat_id, user.id):
        return
    
    # Hide the question by editing it (replace text with placeholder)
    if session.current_question_message_id:
        try:
            cost = session.current_question_data.get('cost', 0) if session.current_question_data else 0
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=session.current_question_message_id,
                text=msg_question_hidden(cost),
                parse_mode="HTML"
            )
        except Exception:
            pass  # Message might be too old to edit
    
    # Notify that player is answering
    player_name = user.username or user.first_name or "Игрок"
    await message.answer(msg_player_answering(player_name))
    
    # Set up timeout for answering
    key = (chat_id, user.id)
    
    async def answer_timeout():
        await asyncio.sleep(10)
        # Time's up
        if cancel_answering(chat_id):
            await bot.send_message(chat_id, msg_time_up(player_name))
            # Restore question
            if session.current_question_message_id and session.current_question_data:
                try:
                    cost = session.current_question_data.get('cost', 0)
                    question_text = session.current_question_data.get('question', '')
                    theme_name = session.current_question_data.get('theme_name', 'Тема')
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=session.current_question_message_id,
                        text=msg_question(cost, theme_name, question_text),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        if key in _waiting_for_answer:
            del _waiting_for_answer[key]
    
    # Cancel any existing timeout
    if key in _waiting_for_answer:
        _waiting_for_answer[key].cancel()
    
    _waiting_for_answer[key] = asyncio.create_task(answer_timeout())


@router.message(F.text & ~F.text.startswith("/"))
async def handle_answer_text(message: types.Message, bot: Bot) -> None:
    """Handle text messages as potential answers."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    key = (chat_id, user.id)
    
    # Check if this user is answering
    session = get_session(chat_id)
    if not session or session.state != GameState.PLAYER_ANSWERING:
        return
    
    if session.answering_player_id != user.id:
        return  # Not the answering player
    
    # Cancel timeout
    if key in _waiting_for_answer:
        _waiting_for_answer[key].cancel()
        del _waiting_for_answer[key]
    
    # Check if question is already claimed
    if session.question_claimed:
        await message.answer(msg_question_claimed())
        cancel_answering(chat_id)
        return
    
    # Get question cost before submitting (session state will change)
    cost = session.current_question_data.get('cost', 0) if session.current_question_data else 0
    
    # Submit answer
    answer_text = message.text or ""
    is_correct = submit_answer(chat_id, user.id, answer_text)
    
    if is_correct is None:
        return  # Something went wrong
    
    # Track that this player answered with their answer state (no score update yet)
    if session.answered_players is not None:
        session.answered_players[user.id] = AnswerState.CORRECT if is_correct else AnswerState.INCORRECT
    
    player_name = user.username or user.first_name or "Игрок"
    
    if is_correct:
        await message.answer(msg_correct_answer(player_name))
    else:
        await message.answer(msg_incorrect_answer(player_name))
        
        # Re-show the question by editing the hidden message
        if session.current_question_message_id and session.current_question_data:
            question_cost = session.current_question_data.get('cost', 0)
            question_text = session.current_question_data.get('question', '')
            short_theme_name = session.current_question_data.get('theme_name', 'Тема')
            
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session.current_question_message_id,
                    text=msg_question(question_cost, short_theme_name, question_text),
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Message might be too old to edit


@router.message(Command("yes"))
@router.message(F.text == "да")
async def yes_command(message: types.Message) -> None:
    """Player confirms their answer was correct (score correction phase)."""

    print("yes_command")
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = get_session(chat_id)
    
    if session is not None:
        print("session:", session.answered_players)
        print("session.state:", session.state)
    else:
        print("session is None")

    
    if not session:
        print("session is None")
        return
    
    # Allow score correction in SCORE_CORRECTION state or when PAUSED from SCORE_CORRECTION
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        print(f"not in score correction (state={session.state}, state_before_pause={session.state_before_pause})")
        return
    
    # Check if player answered this question
    if session.answered_players is None or user.id not in session.answered_players:
        return
    
    # Check player's answer state
    answer_state = session.answered_players.get(user.id)
    
    if answer_state == AnswerState.CORRECT:
        await message.answer(msg_answer_already_correct())
        return
    
    # Mark question as claimed
    session.question_claimed = True
    
    # Get answer order (dicts maintain insertion order in Python 3.7+)
    answer_order = list(session.answered_players.keys())
    user_position = answer_order.index(user.id)
    
    # Update all players' states based on their position relative to the claimer
    for i, player_id in enumerate(answer_order):
        if player_id == user.id:
            session.answered_players[player_id] = AnswerState.CORRECT
        elif session.answered_players[player_id] == AnswerState.CONFIRMED_DOESNT_COUNT:
            # Preserve CONFIRMED_DOESNT_COUNT - player already confirmed they don't count
            pass
        elif i < user_position:
            # Players who answered before → INCORRECT
            session.answered_players[player_id] = AnswerState.INCORRECT
        else:
            # Players who answered after → DOESNT_COUNT
            session.answered_players[player_id] = AnswerState.DOESNT_COUNT
    
    player_name = user.username or user.first_name or "Игрок"
    await message.answer(msg_answer_confirmed(player_name))


@router.message(Command("no"))
@router.message(F.text == "нет")
async def no_command(message: types.Message) -> None:
    """Player confirms their answer was wrong (score correction phase)."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = get_session(chat_id)
    
    if not session:
        return
    
    # Allow score correction in SCORE_CORRECTION state or when PAUSED from SCORE_CORRECTION
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        print(f"not in score correction (state={session.state}, state_before_pause={session.state_before_pause})")
        return
    
    # Check if player answered this question
    if session.answered_players is None or user.id not in session.answered_players:
        return
    
    # Check player's answer state
    answer_state = session.answered_players.get(user.id)
    
    if answer_state == AnswerState.INCORRECT:
        await message.answer(msg_answer_already_incorrect())
        return
    
    # Update player's state to incorrect
    session.answered_players[user.id] = AnswerState.INCORRECT
    
    player_name = user.username or user.first_name or "Игрок"
    await message.answer(msg_answer_rejected(player_name))


@router.message(Command("accidentally"))
@router.message(F.text == "случайно")
@router.message(F.text == "случ")
async def accidentally_command(message: types.Message) -> None:
    """Player marks their answer as accidental (won't be changed to incorrect by /yes)."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = get_session(chat_id)
    
    if not session:
        return
    
    # Allow score correction in SCORE_CORRECTION state or when PAUSED from SCORE_CORRECTION
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        print(f"not in score correction (state={session.state}, state_before_pause={session.state_before_pause})")
        return
    
    # Check if player answered this question
    if session.answered_players is None or user.id not in session.answered_players:
        return
    
    # Check player's answer state
    answer_state = session.answered_players.get(user.id)
    
    if answer_state == AnswerState.CONFIRMED_DOESNT_COUNT:
        await message.answer(msg_answer_already_accidental())
        return
    
    # Update player's state to confirmed doesn't count (won't be changed by /yes)
    session.answered_players[user.id] = AnswerState.CONFIRMED_DOESNT_COUNT
    
    player_name = user.username or user.first_name or "Игрок"
    await message.answer(msg_answer_marked_accidental(player_name))

