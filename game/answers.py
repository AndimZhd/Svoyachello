import re
import unicodedata

from .types import GameState, AnswerState
from .sessions import session_manager


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text)
    # Remove diacritics
    text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Keep only letters, numbers, and spaces
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def remove_brackets(text: str) -> str:
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    return text.strip()


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def get_max_allowed_distance(text_length: int) -> int:
    """Get maximum allowed Levenshtein distance based on text length."""
    if text_length <= 4:
        return 0
    if text_length <= 12:
        return 1
    else:
        return 2


def fuzzy_match(user: str, correct: str) -> bool:
    """Check if user answer matches correct answer with allowed typos."""
    if not user or not correct:
        return False
    
    distance = levenshtein_distance(user, correct)
    max_allowed = get_max_allowed_distance(len(correct))
    
    return distance <= max_allowed


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
        if u and c:
            # Exact containment
            if c in u:
                return True
            # Fuzzy match for exact answer
            if fuzzy_match(u, c):
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
    session.timer_extension = 15.0
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
    
    session.timer_extension = 8.0
    
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

