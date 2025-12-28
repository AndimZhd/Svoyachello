import asyncio

from aiogram import Bot, Router, types, F
from aiogram.filters import Command

from database.players import get_player_by_telegram_id
from database.games import bulk_update_player_scores, get_game_scores
from database.player_rights import ensure_player_rights
from game import session_manager, GameState, AnswerState
from game import answers as game_answers
from game import dispute

import messages.game_messages as gm

router = Router()

_waiting_for_answer: dict[tuple[int, int], asyncio.Task] = {}


async def is_spectator(chat_id: int, telegram_id: int) -> bool:
    player = await get_player_by_telegram_id(telegram_id)
    if not player:
        return False
    return session_manager.is_spectator(chat_id, player['id'])


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
        return
    
    player = await get_player_by_telegram_id(user.id)
    if not player or player['id'] not in session.players:
        return
    
    if await is_spectator(chat_id, user.id):
        return
    
    if session.answered_players is not None and user.id in session.answered_players:
        return
    
    if not game_answers.start_player_answering(chat_id, user.id):
        return
    
    if session.current_question_message_id:
        try:
            cost = session.current_question_data.get('cost', 0) if session.current_question_data else 0
            form = session.current_question_data.get('form', '') if session.current_question_data else ''
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=session.current_question_message_id,
                text=gm.msg_question_hidden(cost, form),
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    
    try:
        await message.answer(gm.msg_player_answering(player_name))
    except Exception:
        # If we can't send the message, still proceed with the answer logic
        pass
    
    key = (chat_id, user.id)
    
    async def answer_timeout():
        await asyncio.sleep(10)
        if game_answers.cancel_answering(chat_id):
            if session.answered_players is not None:
                session.answered_players[user.id] = AnswerState.INCORRECT
            try:
                await bot.send_message(chat_id, gm.msg_time_up(player_name))
                await restore_question_message(bot, chat_id, session)
            except Exception:
                # If message send fails, continue anyway
                pass
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
    
    if session.dispute_player_id == user.id:
        return
    
    if session.disputed_players and user.id in session.disputed_players:
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
    
    if session.dispute_player_id == user.id:
        return
    
    if session.disputed_players and user.id in session.disputed_players:
        return
    
    if not dispute.mark_answer_incorrect(session, user.id):
        return
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_answer_confirmed(player_name))
    
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
    
    if session.dispute_player_id == user.id:
        return
    
    if session.disputed_players and user.id in session.disputed_players:
        return
    
    if not dispute.mark_answer_accidental(session, user.id):
        return
    
    player_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Игрок"
    await message.answer(gm.msg_answer_confirmed(player_name))
    
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
    
    if await is_spectator(chat_id, user.id):
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

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Ответьте на сообщение с ответом игрока, чтобы оспорить его.")
        return
    
    target = message.reply_to_message.from_user
    player_answer = message.reply_to_message.text or "???"
    
    if target.is_bot or not session.answered_players or target.id not in session.answered_players:
        await message.answer("Этот игрок не отвечал на текущий вопрос.")
        return
    
    target_user_id = target.id
    target_name = f"{target.first_name or ''} {target.last_name or ''}".strip() or target.username or "Игрок"
    
    correct_answer = session.current_question_data.get('answer', '???') if session.current_question_data else '???'
    
    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"Засчитать ответ «{player_answer}»?\n(Правильный ответ: {correct_answer})",
        options=["✅ Да, засчитать", "❌ Нет, не засчитывать"],
        is_anonymous=False,
        allows_multiple_answers=False
    )
    
    if not poll_msg.poll:
        await message.answer("Ошибка создания голосования.")
        return
    
    poll_id = poll_msg.poll.id
    session.dispute_poll_id = poll_id
    session.dispute_player_id = target_user_id
    session.dispute_votes = {}
    session_manager.register_poll(poll_id, chat_id)
    
    if session.disputed_players is None:
        session.disputed_players = set()
    session.disputed_players.add(target_user_id)
    
    session.timer_extension = 10.0
    
    async def auto_apply_dispute():
        await asyncio.sleep(10)
        current_session = session_manager.get(chat_id)
        if current_session and current_session.dispute_poll_id == poll_id:
            await dispute.apply_dispute_result(current_session, bot)
    
    asyncio.create_task(auto_apply_dispute())


@router.poll_answer()
async def handle_poll_answer(poll_answer, bot: Bot) -> None:
    chat_id = session_manager.get_chat_by_poll(poll_answer.poll_id)
    if not chat_id:
        return
    
    session = session_manager.get(chat_id)
    if not session:
        return
    
    user_id = poll_answer.user.id
    if not poll_answer.option_ids:
        return
    
    vote = poll_answer.option_ids[0] == 0
    
    if session.dispute_poll_id == poll_answer.poll_id:
        if session.dispute_votes is not None:
            session.dispute_votes[user_id] = vote
            if len(session.dispute_votes) >= len(session.players):
                await dispute.apply_dispute_result(session, bot)
    
    elif session.kick_poll_id == poll_answer.poll_id:
        if session.kick_votes is not None:
            session.kick_votes[user_id] = vote
            if len(session.kick_votes) >= len(session.players):
                await apply_kick_result(session, bot)


async def apply_kick_result(session, bot: Bot) -> None:
    if session.kick_votes is None or session.kick_player_id is None:
        if session.kick_poll_id:
            session_manager.unregister_poll(session.kick_poll_id)
        session.kick_poll_id = None
        session.kick_player_id = None
        session.kick_votes = None
        return
    
    yes_votes = sum(1 for v in session.kick_votes.values() if v)
    total_votes = len(session.kick_votes)
    
    if yes_votes > total_votes / 2:
        try:
            await bot.ban_chat_member(session.game_chat_id, session.kick_player_id)
        except Exception:
            pass
        
        if session.kicked_players is None:
            session.kicked_players = set()
        session.kicked_players.add(session.kick_player_id)
        
        await bot.send_message(session.game_chat_id, "🚪 Игрок исключён из игры.")
    else:
        await bot.send_message(session.game_chat_id, "Голосование не прошло. Игрок остаётся в игре.")
    
    if session.kick_poll_id:
        session_manager.unregister_poll(session.kick_poll_id)
    session.kick_poll_id = None
    session.kick_player_id = None
    session.kick_votes = None


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
    
    rights = await ensure_player_rights(user.id)
    if rights and not rights['can_correct']:
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
    
    if amount < -100 or amount > 100:
        await message.answer("Значение должно быть от -100 до 100.")
        return
    
    if amount % 10 != 0:
        await message.answer("Значение должно быть кратно 10.")
        return
    
    player = await get_player_by_telegram_id(user.id)
    if not player or player['id'] not in session.players:
        await message.answer("Вы не являетесь игроком этой игры.")
        return
    
    scores = await get_game_scores(chat_id)
    current_score = int(scores.get(str(player['id']), 0))
    new_score = current_score + amount
    
    if new_score > 10000:
        new_score = 10000
        amount = new_score - current_score
    
    if new_score < -10000:
        new_score = -10000
        amount = new_score - current_score
    
    if amount == 0:
        return
    
    await bulk_update_player_scores(chat_id, {player['id']: amount})
    
    if session.player_abs_scores is not None:
        session.player_abs_scores[player['id']] = session.player_abs_scores.get(player['id'], 0) + amount
    
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
