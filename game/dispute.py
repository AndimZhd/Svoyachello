from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot

if TYPE_CHECKING:
    from .types import GameSession

from .types import AnswerState


def mark_answer_correct(session: GameSession, player_telegram_id: int) -> bool:
    if not session.answered_players or player_telegram_id not in session.answered_players:
        return False
    
    if session.answered_players.get(player_telegram_id) == AnswerState.CORRECT:
        return False
    
    session.question_claimed = True
    
    answer_order = list(session.answered_players.keys())
    user_position = answer_order.index(player_telegram_id)
    
    for i, pid in enumerate(answer_order):
        if pid == player_telegram_id:
            session.answered_players[pid] = AnswerState.CORRECT
        elif session.answered_players[pid] == AnswerState.CONFIRMED_DOESNT_COUNT:
            pass
        elif i < user_position:
            session.answered_players[pid] = AnswerState.INCORRECT
        else:
            session.answered_players[pid] = AnswerState.DOESNT_COUNT
    
    return True


def mark_answer_incorrect(session: GameSession, player_telegram_id: int) -> bool:
    if not session.answered_players or player_telegram_id not in session.answered_players:
        return False
    
    if session.answered_players.get(player_telegram_id) == AnswerState.INCORRECT:
        return False
    
    session.answered_players[player_telegram_id] = AnswerState.INCORRECT
    return True


def mark_answer_accidental(session: GameSession, player_telegram_id: int) -> bool:
    if not session.answered_players or player_telegram_id not in session.answered_players:
        return False
    
    if session.answered_players.get(player_telegram_id) == AnswerState.CONFIRMED_DOESNT_COUNT:
        return False
    
    session.answered_players[player_telegram_id] = AnswerState.CONFIRMED_DOESNT_COUNT
    return True


async def apply_dispute_result(session: GameSession, bot: Bot) -> None:
    if not session.dispute_votes or session.dispute_player_id is None:
        session.dispute_poll_id = None
        session.dispute_player_id = None
        session.dispute_votes = None
        return
    
    yes_votes = sum(1 for v in session.dispute_votes.values() if v)
    no_votes = sum(1 for v in session.dispute_votes.values() if not v)
    
    player_id = session.dispute_player_id
    
    if yes_votes > no_votes:
        mark_answer_correct(session, player_id)
        await bot.send_message(
            session.game_chat_id,
            f"🗳 Результат голосования: ✅ засчитать ({yes_votes} за, {no_votes} против)"
        )
    elif no_votes > yes_votes:
        mark_answer_incorrect(session, player_id)
        await bot.send_message(
            session.game_chat_id,
            f"🗳 Результат голосования: ❌ не засчитывать ({yes_votes} за, {no_votes} против)"
        )
    else:
        mark_answer_accidental(session, player_id)
        await bot.send_message(
            session.game_chat_id,
            f"🗳 Голоса разделились поровну ({yes_votes}:{no_votes}). Ответ не засчитывается."
        )
    
    session.dispute_poll_id = None
    session.dispute_player_id = None
    session.dispute_votes = None
