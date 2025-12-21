import asyncio
from enum import Enum
from dataclasses import dataclass
from uuid import UUID

from aiogram import Bot

from database.games import (
    get_game_by_chat_id,
    get_current_position,
    set_current_position,
    update_game_status,
    bulk_update_player_scores,
)
from database.packs import get_pack_by_short_name
from database.players import get_player_by_telegram_id
from messages import (
    msg_pack_not_found,
    msg_score_summary,
    msg_current_scores,
    msg_pack_info,
    msg_theme_name,
    msg_attention_question,
    msg_question,
    msg_answer,
    msg_score_correction,
    msg_game_over,
    msg_error,
)


class GameState(Enum):
    """Game states."""
    IDLE = "idle"
    SHOWING_THEME = "showing_theme"
    SHOWING_QUESTION = "showing_question"
    WAITING_ANSWER = "waiting_answer"
    PLAYER_ANSWERING = "player_answering"
    SHOWING_ANSWER = "showing_answer"
    SCORE_CORRECTION = "score_correction"
    PAUSED = "paused"
    GAME_OVER = "game_over"


class AnswerState(Enum):
    """Answer states for score correction."""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    DOESNT_COUNT = "doesnt_count"
    CONFIRMED_DOESNT_COUNT = "confirmed_doesnt_count"  # Player confirmed, won't be changed to incorrect


@dataclass
class GameSession:
    """Represents an active game session."""
    game_chat_id: int  # The game chat where questions are sent
    origin_chat_id: int  # The original chat where game was registered
    pack_file: dict
    pack_themes: list[int]
    players: list[UUID]
    state: GameState = GameState.IDLE
    state_before_pause: GameState = GameState.IDLE
    current_theme_idx: int = 0
    current_question_idx: int = 0
    task: asyncio.Task | None = None
    pause_event: asyncio.Event | None = None  # Set when NOT paused (clear to pause)
    # Answer handling
    current_question_message_id: int | None = None
    current_question_data: dict | None = None  # Current question with answer
    answering_player_id: int | None = None  # Telegram ID of player answering
    answer_event: asyncio.Event | None = None  # Set when answer is received
    answer_correct: bool | None = None  # Result of answer validation
    # Score correction
    answered_players: dict[int, AnswerState] | None = None  # {telegram_id: AnswerState}
    question_claimed: bool = False  # True if someone pressed /yes (question is claimed)


# Active game sessions
_active_sessions: dict[int, GameSession] = {}


async def start_game_session(game_chat_id: int, origin_chat_id: int, bot: Bot) -> None:
    """Start a new game session when all players have joined."""
    # Get game info (game is now stored under game_chat_id after transfer)
    game = await get_game_by_chat_id(game_chat_id)
    if not game:
        return
    
    # Get pack info
    pack = await get_pack_by_short_name(game['pack_short_name'])
    if not pack:
        await bot.send_message(game_chat_id, msg_pack_not_found())
        return
    
    print(f"Game: {game}")
    
    # Get current position (in case of resume)
    # Game is now stored under game_chat_id after transfer
    position = await get_current_position(game_chat_id)
    theme_idx = position.get('theme', 0) if isinstance(position, dict) else 0
    question_idx = position.get('question', 0) if isinstance(position, dict) else 0

    print(f"Theme index: {theme_idx}, Question index: {question_idx}")
    
    # Create pause event (set = not paused, clear = paused)
    pause_event = asyncio.Event()
    pause_event.set()  # Start unpaused
    
    # Create answer event (set when player submits answer)
    answer_event = asyncio.Event()
    
    # Create session
    session = GameSession(
        game_chat_id=game_chat_id,
        origin_chat_id=origin_chat_id,
        pack_file=pack['pack_file'],
        pack_themes=game['pack_themes'],
        players=game['players'],
        state=GameState.IDLE,
        current_theme_idx=theme_idx,
        current_question_idx=question_idx,
        pause_event=pause_event,
        answer_event=answer_event,
    )

    print(f"Session: {session}")
    
    _active_sessions[game_chat_id] = session
    
    # Start the game loop
    session.task = asyncio.create_task(game_loop(session, bot))

    print(f"Session started")


async def stop_game_session(game_chat_id: int) -> None:
    """Stop a game session."""
    session = _active_sessions.get(game_chat_id)
    if session and session.task:
        session.task.cancel()
        try:
            await session.task
        except asyncio.CancelledError:
            pass
    
    if game_chat_id in _active_sessions:
        del _active_sessions[game_chat_id]


def stop_all_sessions() -> None:
    """Stop all active game sessions."""
    for session in _active_sessions.values():
        if session.task:
            session.task.cancel()
    _active_sessions.clear()


def get_session(game_chat_id: int) -> GameSession | None:
    """Get active game session."""
    return _active_sessions.get(game_chat_id)


def pause_game_session(game_chat_id: int) -> bool:
    """Pause a game session. Returns True if paused, False if not found or already paused."""
    session = _active_sessions.get(game_chat_id)
    if not session or not session.pause_event:
        return False
    
    if session.state == GameState.PAUSED:
        return False  # Already paused
    
    session.state_before_pause = session.state
    session.state = GameState.PAUSED
    session.pause_event.clear()  # Clear = paused
    return True


def resume_game_session(game_chat_id: int) -> bool:
    """Resume a paused game session. Returns True if resumed, False if not found or not paused."""
    session = _active_sessions.get(game_chat_id)
    if not session or not session.pause_event:
        return False
    
    if session.state != GameState.PAUSED:
        return False  # Not paused
    
    session.state = session.state_before_pause
    session.pause_event.set()  # Set = unpaused
    return True


async def wait_with_pause(session: GameSession, seconds: float) -> None:
    """Sleep for given seconds, but pause if game is paused."""
    if not session.pause_event:
        await asyncio.sleep(seconds)
        return
    
    # Wait in small increments, checking for pause
    remaining = seconds
    while remaining > 0:
        # Check if paused
        if not session.pause_event.is_set():
            # Wait until unpaused
            await session.pause_event.wait()
        
        # Sleep in 0.5 second increments
        sleep_time = min(0.5, remaining)
        await asyncio.sleep(sleep_time)
        
        # Only decrement if not paused
        if session.pause_event.is_set():
            remaining -= sleep_time


async def wait_for_answer_or_timeout(session: GameSession, seconds: float) -> bool:
    """Wait for answer event or timeout. Returns True if answered, False if timeout."""
    if not session.answer_event or not session.pause_event:
        await asyncio.sleep(seconds)
        return False
    
    remaining = seconds
    while remaining > 0:
        # Check if paused
        if not session.pause_event.is_set():
            await session.pause_event.wait()
            continue
        
        # Check if answer received
        if session.answer_event.is_set():
            return True
        
        # Sleep in small increments
        sleep_time = min(0.1, remaining)
        await asyncio.sleep(sleep_time)
        remaining -= sleep_time
    
    return False


def start_player_answering(game_chat_id: int, player_telegram_id: int) -> bool:
    """Start answering mode for a player. Returns True if successful."""
    session = _active_sessions.get(game_chat_id)
    if not session:
        return False
    
    if session.state != GameState.WAITING_ANSWER:
        return False
    
    if session.answering_player_id is not None:
        return False  # Someone already answering
    
    session.answering_player_id = player_telegram_id
    session.state = GameState.PLAYER_ANSWERING
    return True


def submit_answer(game_chat_id: int, player_telegram_id: int, answer_text: str) -> bool | None:
    """Submit an answer. Returns True if correct, False if wrong, None if not in answering state."""
    session = _active_sessions.get(game_chat_id)
    if not session:
        return None
    
    if session.state != GameState.PLAYER_ANSWERING:
        return None
    
    if session.answering_player_id != player_telegram_id:
        return None  # Wrong player
    
    if not session.current_question_data:
        return None
    
    # Validate answer
    correct_answer = session.current_question_data.get('answer', '').lower().strip()
    user_answer = answer_text.lower().strip()
    
    # Check if answer matches (simple contains check for now)
    # Handle format "answer1/answer2" for multiple accepted answers
    accepted_answers = [a.strip() for a in correct_answer.split('/')]
    is_correct = any(user_answer in a or a in user_answer for a in accepted_answers if a)
    
    session.answer_correct = is_correct
    
    # Add player to answered_players BEFORE setting event (to avoid race condition)
    if session.answered_players is not None:
        session.answered_players[player_telegram_id] = AnswerState.CORRECT if is_correct else AnswerState.INCORRECT
    
    session.state = GameState.WAITING_ANSWER  # Return to waiting state
    session.answering_player_id = None  # Clear answering player
    
    # Only signal completion if answer is correct
    # If incorrect, let other players try
    if is_correct and session.answer_event:
        session.answer_event.set()
    
    return is_correct


def cancel_answering(game_chat_id: int) -> bool:
    """Cancel answering mode (player didn't answer in time). Returns True if cancelled."""
    session = _active_sessions.get(game_chat_id)
    if not session:
        return False
    
    if session.state != GameState.PLAYER_ANSWERING:
        return False
    
    session.answering_player_id = None
    session.state = GameState.WAITING_ANSWER
    return True


async def finalize_question_scores(session: GameSession, cost: int, bot: Bot) -> None:
    """Finalize scores for a question based on answer states. Called once after SCORE_CORRECTION phase."""
    if not session.answered_players:
        return
    
    score_changes: dict[UUID, int] = {}
    score_messages = []
    
    for telegram_id, answer_state in session.answered_players.items():
        player = await get_player_by_telegram_id(telegram_id)
        if not player:
            continue
        
        if answer_state == AnswerState.CORRECT:
            score_changes[player['id']] = cost
            score_messages.append(f"✅ +{cost}")
        elif answer_state == AnswerState.INCORRECT:
            score_changes[player['id']] = -cost
            score_messages.append(f"❌ -{cost}")
        # DOESNT_COUNT and CONFIRMED_DOESNT_COUNT = no score change
    
    # Single bulk update for all score changes
    if score_changes:
        await bulk_update_player_scores(session.game_chat_id, score_changes)
    
    if score_messages:
        await bot.send_message(
            session.game_chat_id,
            msg_score_summary(score_messages)
        )


async def show_current_scores(session: GameSession, bot: Bot) -> None:
    """Show current scores for all players."""
    from database.games import get_game_scores
    from database.players import get_players_telegram_ids
    
    scores = await get_game_scores(session.game_chat_id)
    players_info = await get_players_telegram_ids(session.players)
    
    # Build UUID to username map
    uuid_to_name: dict[str, str] = {}
    for i, player_uuid in enumerate(session.players):
        if i < len(players_info):
            uuid_to_name[str(player_uuid)] = players_info[i].get('username') or "Игрок"
    
    # Build score display sorted by score descending
    score_lines = []
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        score = int(scores.get(uuid_str, 0))
        name = uuid_to_name.get(uuid_str, "Игрок")
        score_lines.append((score, f"@{name}: {score}"))
    
    # Sort by score descending
    score_lines.sort(key=lambda x: x[0], reverse=True)
    
    if score_lines:
        await bot.send_message(
            session.game_chat_id,
            msg_current_scores([line for _, line in score_lines])
        )


async def game_loop(session: GameSession, bot: Bot) -> None:
    """Main game loop - runs through themes and questions."""
    try:
        themes = session.pack_file.get('themes', [])
        theme_names = session.pack_file.get('theme_names', [])
        pack_info = session.pack_file.get('info', '')
        
        # Show pack info at the start
        if pack_info and session.current_theme_idx == 0 and session.current_question_idx == 0:
            await bot.send_message(
                session.game_chat_id,
                msg_pack_info(pack_info),
                parse_mode="HTML"
            )
            await wait_with_pause(session, 3)
        
        # Start from current position
        theme_idx = session.current_theme_idx
        
        while theme_idx < len(session.pack_themes):
            pack_theme_index = session.pack_themes[theme_idx]
            
            # Validate theme index
            if pack_theme_index >= len(themes):
                theme_idx += 1
                continue
            
            theme = themes[pack_theme_index]
            theme_name = theme_names[pack_theme_index] if pack_theme_index < len(theme_names) else theme.get('name', f'Тема {theme_idx + 1}')
            
            # Show theme
            session.state = GameState.SHOWING_THEME
            await bot.send_message(
                session.game_chat_id,
                msg_theme_name(theme_name),
                parse_mode="HTML"
            )
            await wait_with_pause(session, 2)
            
            questions = theme.get('questions', [])
            question_idx = session.current_question_idx if theme_idx == session.current_theme_idx else 0
            
            while question_idx < len(questions):
                question = questions[question_idx]
                
                # Save position
                await set_current_position(session.game_chat_id, theme_idx, question_idx)
                session.current_theme_idx = theme_idx
                session.current_question_idx = question_idx
                
                # Announce question
                await bot.send_message(session.game_chat_id, msg_attention_question())
                await wait_with_pause(session, 1)
                
                # Show question
                session.state = GameState.SHOWING_QUESTION
                cost = question.get('cost', (question_idx + 1) * 10)
                question_text = question.get('question', '')
                
                # Get short theme name (without author)
                short_theme_name = theme.get('name', f'Тема {theme_idx + 1}')
                
                question_msg = await bot.send_message(
                    session.game_chat_id,
                    msg_question(cost, short_theme_name, question_text),
                    parse_mode="HTML"
                )
                
                # Store question data for answer validation (include theme name for re-display)
                session.current_question_message_id = question_msg.message_id
                session.current_question_data = {**question, 'theme_name': short_theme_name}
                session.answering_player_id = None
                session.answer_correct = None
                session.answered_players = {}
                session.question_claimed = False
                if session.answer_event:
                    session.answer_event.clear()
                
                # Wait for answer (20 seconds) or player pressing /answer
                session.state = GameState.WAITING_ANSWER
                answered = await wait_for_answer_or_timeout(session, 20)
                
                # Show answer
                session.state = GameState.SHOWING_ANSWER
                answer_text = question.get('answer', '')
                comment = question.get('comment', '')
                
                await bot.send_message(session.game_chat_id, msg_answer(answer_text, comment))
                
                # Score correction phase (5 seconds)
                if session.answered_players:
                    session.state = GameState.SCORE_CORRECTION
                    await bot.send_message(
                        session.game_chat_id,
                        msg_score_correction()
                    )
                    await wait_with_pause(session, 5)
                    
                    # Finalize scores based on final answer states
                    await finalize_question_scores(session, cost, bot)
                else:
                    await wait_with_pause(session, 3)
                
                # Show current scores after each question
                await show_current_scores(session, bot)
                
                # Reset question data
                session.current_question_message_id = None
                session.current_question_data = None
                session.answering_player_id = None
                session.answered_players = None
                session.question_claimed = False
                
                question_idx += 1
            
            # Reset question index for next theme
            session.current_question_idx = 0
            theme_idx += 1
        
        # Game over
        session.state = GameState.GAME_OVER
        await bot.send_message(session.game_chat_id, msg_game_over())
        await update_game_status(session.game_chat_id, 'finished')
        
        # Clean up
        if session.game_chat_id in _active_sessions:
            del _active_sessions[session.game_chat_id]
            
    except asyncio.CancelledError:
        # Game was stopped
        raise
    except Exception as e:
        await bot.send_message(session.game_chat_id, msg_error(str(e)))
        session.state = GameState.IDLE

