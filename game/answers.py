import re
import unicodedata

from .types import GameState, AnswerState
from .sessions import session_manager


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower().strip()


def remove_brackets(text: str) -> str:
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    return text.strip()


def answers_match(user: str, correct: str) -> bool:
    user_norm = normalize_text(user)
    correct_norm = normalize_text(correct)
    
    user_no_brackets = normalize_text(remove_brackets(user))
    correct_no_brackets = normalize_text(remove_brackets(correct))
    
    combinations = [
        (user_norm, correct_norm),
        (user_no_brackets, correct_norm),
        (user_norm, correct_no_brackets),
        (user_no_brackets, correct_no_brackets),
    ]
    
    for u, c in combinations:
        if u and c and (u in c or c in u):
            return True
    return False


def start_player_answering(game_chat_id: int, player_telegram_id: int) -> bool:
    session = session_manager.get(game_chat_id)
    if not session:
        return False
    
    if session.state != GameState.WAITING_ANSWER:
        return False
    
    if session.answering_player_id is not None:
        return False
    
    session.answering_player_id = player_telegram_id
    session.state = GameState.PLAYER_ANSWERING
    return True


def submit_answer(game_chat_id: int, player_telegram_id: int, answer_text: str) -> bool | None:
    session = session_manager.get(game_chat_id)
    if not session:
        return None
    
    if session.state != GameState.PLAYER_ANSWERING:
        return None
    
    if session.answering_player_id != player_telegram_id:
        return None
    
    if not session.current_question_data:
        return None
    
    raw_correct = session.current_question_data.get('answer', '')
    
    accepted_answers = [a.strip() for a in raw_correct.split('/')]
    is_correct = any(answers_match(answer_text, a) for a in accepted_answers if a)
    
    session.answer_correct = is_correct
    
    if session.answered_players is not None:
        session.answered_players[player_telegram_id] = AnswerState.CORRECT if is_correct else AnswerState.INCORRECT
    
    session.state = GameState.WAITING_ANSWER
    session.answering_player_id = None
    
    session.timer_extension = 5.0
    
    if is_correct and session.answer_event:
        session.answer_event.set()
    
    return is_correct


def cancel_answering(game_chat_id: int) -> bool:
    session = session_manager.get(game_chat_id)
    if not session:
        return False
    
    if session.state != GameState.PLAYER_ANSWERING:
        return False
    
    session.answering_player_id = None
    session.state = GameState.WAITING_ANSWER
    session.timer_extension = 10
    return True

