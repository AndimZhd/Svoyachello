import asyncio

from aiogram import Bot, Router, types, F
from aiogram.filters import Command

from database.players import get_player_by_telegram_id
from database.games import bulk_update_player_scores
from game import session_manager, GameState, AnswerState
from game import answers as game_answers
from game import dispute

import messages.game_messages as gm

router = Router()

_waiting_for_answer: dict[tuple[int, int], asyncio.Task] = {}


async def restore_question_message(bot: Bot, chat_id: int, session) -> None:
    if not session.current_question_message_id or not session.current_question_data:
        return
    
    cost = session.current_question_data.get('cost', 0)
    theme_name = session.current_question_data.get('theme_name', 'Тема')
    question_text = session.current_question_data.get('question', '')
    
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=session.current_question_message_id,
            text=gm.msg_question(cost, theme_name, question_text),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(Command("answer"))
@router.message(F.text == "+")
async def answer_command(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    session = session_manager.get(chat_id)
    if not session:
        return
    
    if session.state != GameState.WAITING_ANSWER:
        if session.state == GameState.PLAYER_ANSWERING:
            await message.answer(gm.msg_someone_answering())
        return
    
    player = await get_player_by_telegram_id(user.id)
    if not player or player['id'] not in session.players:
        return
    
    if session.answered_players is not None and user.id in session.answered_players:
        return
    
    if not game_answers.start_player_answering(chat_id, user.id):
        return
    
    if session.current_question_message_id:
        try:
            cost = session.current_question_data.get('cost', 0) if session.current_question_data else 0
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=session.current_question_message_id,
                text=gm.msg_question_hidden(cost),
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_player_answering(player_name))
    
    key = (chat_id, user.id)
    
    async def answer_timeout():
        await asyncio.sleep(10)
        if game_answers.cancel_answering(chat_id):
            if session.answered_players is not None:
                session.answered_players[user.id] = AnswerState.INCORRECT
            await bot.send_message(chat_id, gm.msg_time_up(player_name))
            await restore_question_message(bot, chat_id, session)
        if key in _waiting_for_answer:
            del _waiting_for_answer[key]
    
    if key in _waiting_for_answer:
        _waiting_for_answer[key].cancel()
    
    _waiting_for_answer[key] = asyncio.create_task(answer_timeout())


@router.message(Command("yes"))
@router.message(F.text.lower() == "да")
async def yes_command(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        return
    
    if not dispute.mark_answer_correct(session, user.id):
        return
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_answer_confirmed(player_name))
    
    session.timer_extension = 5.0


@router.message(Command("no"))
@router.message(F.text.lower() == "нет")
async def no_command(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        return
    
    if not dispute.mark_answer_incorrect(session, user.id):
        return
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_answer_rejected(player_name))
    
    session.timer_extension = 5.0


@router.message(Command("accidentally"))
@router.message(F.text.lower() == "случайно")
@router.message(F.text.lower() == "случ")
async def accidentally_command(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        return
    
    if not dispute.mark_answer_accidental(session, user.id):
        return
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_answer_marked_accidental(player_name))
    
    session.timer_extension = 5.0


@router.message(Command("dispute"))
@router.message(F.text.lower() == "спор")
async def dispute_command(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    in_score_correction = (
        session.state == GameState.SCORE_CORRECTION or
        (session.state == GameState.PAUSED and session.state_before_pause == GameState.SCORE_CORRECTION)
    )
    if not in_score_correction:
        return
    
    if session.dispute_poll_id is not None:
        await message.answer("Уже идёт голосование по другому спору.")
        return
    
    target_user_id = None
    target_name = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = user
    
    if not target.is_bot and session.answered_players and target.id in session.answered_players:
        target_user_id = target.id
        target_name = f"{target.first_name or ''} {target.last_name or ''}".strip() or target.username or "Игрок"
    
    if target_user_id is None and session.answered_players:
        answered_list = list(session.answered_players.keys())
        if answered_list:
            target_user_id = answered_list[-1]
            target_name = "последнего ответившего"
    
    if target_user_id is None:
        await message.answer("Не удалось определить игрока для спора.")
        return
    
    correct_answer = session.current_question_data.get('answer', '???') if session.current_question_data else '???'
    
    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"Считать ответ {target_name} правильным?\n(Правильный ответ: {correct_answer})",
        options=["✅ Да, засчитать", "❌ Нет, не засчитывать"],
        is_anonymous=False,
        allows_multiple_answers=False
    )
    
    if not poll_msg.poll:
        await message.answer("Ошибка создания голосования.")
        return
    
    session.dispute_poll_id = poll_msg.poll.id
    session.dispute_player_id = target_user_id
    session.dispute_votes = {}
    
    session.timer_extension = 15.0
    
    await message.answer("🗳 Голосование начато! У вас есть 15 секунд.")


@router.poll_answer()
async def handle_poll_answer(poll_answer) -> None:
    for chat_id, session in session_manager.get_all().items():
        if session.dispute_poll_id == poll_answer.poll_id:
            user_id = poll_answer.user.id
            if poll_answer.option_ids:
                vote = poll_answer.option_ids[0] == 0
                if session.dispute_votes is not None:
                    session.dispute_votes[user_id] = vote
            break


@router.message(Command("correct"))
@router.message(F.text.func(lambda t: t.lower().startswith("исправить") if t else False))
async def correct_command(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    if session.state != GameState.PAUSED:
        return
    
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return
    
    try:
        amount = int(parts[1])
    except ValueError:
        await message.answer("Укажите число. Например: /correct 10 или /correct -20")
        return
    
    player = await get_player_by_telegram_id(user.id)
    if not player or player['id'] not in session.players:
        await message.answer("Вы не являетесь игроком этой игры.")
        return
    
    await bulk_update_player_scores(chat_id, {player['id']: amount})
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    sign = "+" if amount >= 0 else ""
    await message.answer(f"✏️ Счёт игрока {player_name} изменён на {sign}{amount}")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_answer_text(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    key = (chat_id, user.id)
    
    session = session_manager.get(chat_id)
    if not session or session.state != GameState.PLAYER_ANSWERING:
        return
    
    if session.answering_player_id != user.id:
        return
    
    if key in _waiting_for_answer:
        _waiting_for_answer[key].cancel()
        del _waiting_for_answer[key]
    
    if session.question_claimed:
        await message.answer(gm.msg_question_claimed())
        game_answers.cancel_answering(chat_id)
        return
    
    cost = session.current_question_data.get('cost', 0) if session.current_question_data else 0
    
    answer_text = message.text or ""
    is_correct = game_answers.submit_answer(chat_id, user.id, answer_text)
    
    if is_correct is None:
        return
    
    if session.answered_players is not None:
        session.answered_players[user.id] = AnswerState.CORRECT if is_correct else AnswerState.INCORRECT
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    
    if is_correct:
        await message.answer(gm.msg_correct_answer(player_name))
    else:
        await message.answer(gm.msg_incorrect_answer(player_name))
    
    await restore_question_message(bot, chat_id, session)
