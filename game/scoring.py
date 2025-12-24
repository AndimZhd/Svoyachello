from uuid import UUID

from aiogram import Bot

from database import games, players
import messages
from .types import GameSession, AnswerState


async def finalize_question_scores(session: GameSession, cost: int, bot: Bot) -> None:
    if not session.answered_players:
        return
    
    if session.dispute_poll_id is not None and session.dispute_player_id is not None:
        from .dispute import apply_dispute_result
        await apply_dispute_result(session, bot)
    
    telegram_ids = list(session.answered_players.keys())
    players_by_telegram_id = await players.get_players_by_telegram_ids(telegram_ids)
    
    score_changes: dict[UUID, int] = {}
    score_messages = []
    
    for telegram_id, answer_state in session.answered_players.items():
        player = players_by_telegram_id.get(telegram_id)
        if not player:
            continue
        
        player_uuid = player['id']
        
        if answer_state == AnswerState.CORRECT:
            score_changes[player_uuid] = cost
            score_messages.append(f"✅ +{cost}")
            if session.player_correct_answers is not None:
                session.player_correct_answers[telegram_id] = session.player_correct_answers.get(telegram_id, 0) + 1
            if session.player_abs_scores is not None:
                session.player_abs_scores[player_uuid] = session.player_abs_scores.get(player_uuid, 0) + cost
        elif answer_state == AnswerState.INCORRECT:
            score_changes[player_uuid] = -cost
            score_messages.append(f"❌ -{cost}")
            if session.player_wrong_answers is not None:
                session.player_wrong_answers[telegram_id] = session.player_wrong_answers.get(telegram_id, 0) + 1
    
    if score_changes:
        await games.bulk_update_player_scores(session.game_chat_id, score_changes)


async def show_current_scores(session: GameSession, bot: Bot) -> None:
    scores = await games.get_game_scores(session.game_chat_id)
    players_info = await players.get_players_telegram_ids(session.players)
    
    uuid_to_name: dict[str, str] = {}
    for info in players_info:
        first = info.get('first_name') or ''
        last = info.get('last_name') or ''
        full_name = f"{first} {last}".strip()
        uuid_to_name[str(info['id'])] = full_name or info.get('username') or "Игрок"
    
    score_lines = []
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        score = int(scores.get(uuid_str, 0))
        name = uuid_to_name.get(uuid_str, "Игрок")
        score_lines.append((score, f"{name}: {score}"))
    
    score_lines.sort(key=lambda x: x[0], reverse=True)
    
    if score_lines:
        await bot.send_message(
            session.game_chat_id,
            messages.msg_current_scores([line for _, line in score_lines])
        )

