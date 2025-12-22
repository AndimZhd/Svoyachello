import asyncio
import unicodedata
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
    get_game_scores,
    delete_game,
)
from database.game_chats import release_game_chat
from database.packs import get_pack_by_short_name, update_player_pack_history
from database.players import get_player_by_telegram_id, get_players_telegram_ids
from database.statistics import (
    get_statistics_by_player_id,
    update_player_game_stats,
    calculate_elo_changes,
    create_statistics,
)
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
    # Answer statistics per player (telegram_id -> count)
    player_correct_answers: dict[int, int] | None = None
    player_wrong_answers: dict[int, int] | None = None
    player_abs_scores: dict[int, int] | None = None  # Sum of correct answer costs only


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
        player_correct_answers={},
        player_wrong_answers={},
        player_abs_scores={},
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
    
    # Validate answer - normalize to remove accents
    def normalize_text(text: str) -> str:
        """Remove accents and normalize text for comparison."""
        # NFD decomposes characters into base + combining marks
        # Then filter out combining marks (category 'Mn' = Mark, Nonspacing)
        normalized = unicodedata.normalize('NFD', text)
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower().strip()
    
    def remove_brackets(text: str) -> str:
        """Remove content in brackets [] and () including the brackets."""
        import re
        text = re.sub(r'\([^)]*\)', '', text)  # Remove (...)
        text = re.sub(r'\[[^\]]*\]', '', text)  # Remove [...]
        return text.strip()
    
    def answers_match(user: str, correct: str) -> bool:
        """Check if user answer matches correct answer, with or without brackets."""
        # Normalize both
        user_norm = normalize_text(user)
        correct_norm = normalize_text(correct)
        
        # Also prepare versions without brackets
        user_no_brackets = normalize_text(remove_brackets(user))
        correct_no_brackets = normalize_text(remove_brackets(correct))
        
        # Check all combinations
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
    
    raw_correct = session.current_question_data.get('answer', '')
    
    # Check if answer matches
    # Handle format "answer1/answer2" for multiple accepted answers
    accepted_answers = [a.strip() for a in raw_correct.split('/')]
    is_correct = any(answers_match(answer_text, a) for a in accepted_answers if a)
    
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
            # Track correct answer and abs_score
            if session.player_correct_answers is not None:
                session.player_correct_answers[telegram_id] = session.player_correct_answers.get(telegram_id, 0) + 1
            if session.player_abs_scores is not None:
                session.player_abs_scores[telegram_id] = session.player_abs_scores.get(telegram_id, 0) + cost
        elif answer_state == AnswerState.INCORRECT:
            score_changes[player['id']] = -cost
            score_messages.append(f"❌ -{cost}")
            # Track wrong answer
            if session.player_wrong_answers is not None:
                session.player_wrong_answers[telegram_id] = session.player_wrong_answers.get(telegram_id, 0) + 1
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
    scores = await get_game_scores(session.game_chat_id)
    players_info = await get_players_telegram_ids(session.players)
    
    # Build UUID to name map (use full name: first_name + last_name)
    uuid_to_name: dict[str, str] = {}
    for i, player_uuid in enumerate(session.players):
        if i < len(players_info):
            info = players_info[i]
            first = info.get('first_name') or ''
            last = info.get('last_name') or ''
            full_name = f"{first} {last}".strip()
            uuid_to_name[str(player_uuid)] = full_name or info.get('username') or "Игрок"
    
    # Build score display sorted by score descending
    score_lines = []
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        score = int(scores.get(uuid_str, 0))
        name = uuid_to_name.get(uuid_str, "Игрок")
        score_lines.append((score, f"{name}: {score}"))
    
    # Sort by score descending
    score_lines.sort(key=lambda x: x[0], reverse=True)
    
    if score_lines:
        await bot.send_message(
            session.game_chat_id,
            msg_current_scores([line for _, line in score_lines])
        )


async def finalize_game(session: GameSession, bot: Bot) -> None:
    """
    Finalize the game after it ends:
    1. Calculate final scores and determine winner
    2. Calculate ELO changes for all players
    3. Update player statistics
    4. Kick all players from the game chat
    5. Release the game chat and delete the game
    """
    game_chat_id = session.game_chat_id
    
    # Get final scores
    scores = await get_game_scores(game_chat_id)
    
    # Get game info for game ID
    game = await get_game_by_chat_id(game_chat_id)
    if not game:
        return
    
    # Get player info (telegram_id, username) for all players
    players_info = await get_players_telegram_ids(session.players)
    uuid_to_info: dict[str, dict] = {}
    for i, player_uuid in enumerate(session.players):
        if i < len(players_info):
            uuid_to_info[str(player_uuid)] = players_info[i]
    
    # Build player scores and abs_scores as {UUID: score}
    player_scores: dict[UUID, int] = {}
    player_abs_scores: dict[UUID, int] = {}
    for player_uuid in session.players:
        uuid_str = str(player_uuid)
        player_scores[player_uuid] = int(scores.get(uuid_str, 0))
        
        # Get abs_score using telegram_id
        info = uuid_to_info.get(uuid_str, {})
        telegram_id = info.get('telegram_id')
        if telegram_id and session.player_abs_scores:
            player_abs_scores[player_uuid] = session.player_abs_scores.get(telegram_id, 0)
        else:
            player_abs_scores[player_uuid] = 0
    
    # Sort players by game_score, then by abs_score (both descending) for tiebreaking
    sorted_players = sorted(
        session.players,
        key=lambda pid: (player_scores.get(pid, 0), player_abs_scores.get(pid, 0)),
        reverse=True
    )
    
    # Determine winners - top half of players (at least 1)
    num_winners = max(1, len(session.players) // 2)
    winners = set(sorted_players[:num_winners])
    
    # Get current ELO ratings for all players
    player_ratings: dict[UUID, int] = {}
    for player_uuid in session.players:
        stats = await get_statistics_by_player_id(player_uuid)
        if stats:
            player_ratings[player_uuid] = stats.get('elo_rating', 1000)
        else:
            # Create statistics if not exists
            await create_statistics(player_uuid)
            player_ratings[player_uuid] = 1000
    
    # Calculate ELO changes
    elo_changes = calculate_elo_changes(player_ratings, player_scores)
    
    # Update statistics for each player
    for player_uuid in session.players:
        is_winner = player_uuid in winners
        game_score = player_scores.get(player_uuid, 0)
        elo_change = elo_changes.get(player_uuid, 0)
        
        # Get answer counts and abs_score using telegram_id
        info = uuid_to_info.get(str(player_uuid), {})
        telegram_id = info.get('telegram_id')
        correct_answers = 0
        wrong_answers = 0
        abs_score = 0
        if telegram_id:
            if session.player_correct_answers:
                correct_answers = session.player_correct_answers.get(telegram_id, 0)
            if session.player_wrong_answers:
                wrong_answers = session.player_wrong_answers.get(telegram_id, 0)
            if session.player_abs_scores:
                abs_score = session.player_abs_scores.get(telegram_id, 0)
        
        await update_player_game_stats(
            player_id=player_uuid,
            game_score=game_score,
            is_winner=is_winner,
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            abs_score=abs_score,
            elo_change=elo_change
        )
    
    result_lines = []
    for i, player_uuid in enumerate(sorted_players):
        info = uuid_to_info.get(str(player_uuid), {})
        first = info.get('first_name') or ''
        last = info.get('last_name') or ''
        name = f"{first} {last}".strip() or info.get('username') or 'Игрок'
        score = player_scores.get(player_uuid, 0)
        elo_change = elo_changes.get(player_uuid, 0)
        new_elo = player_ratings.get(player_uuid, 1000) + elo_change
        
        # Format ELO change
        elo_str = f"+{elo_change}" if elo_change >= 0 else str(elo_change)
        
        # Medal for top 3
        medal = ""
        if i == 0:
            medal = "🥇 "
        elif i == 1:
            medal = "🥈 "
        elif i == 2:
            medal = "🥉 "
        
        result_lines.append(f"{medal}{name}: {score} очков (ELO: {new_elo} {elo_str})")
    
    results_message = "📊 <b>Итоги игры:</b>\n\n" + "\n".join(result_lines)
    
    await bot.send_message(game_chat_id, results_message, parse_mode="HTML")
    
    # Also send results to the origin chat where the game was registered
    if session.origin_chat_id != game_chat_id:
        try:
            await bot.send_message(session.origin_chat_id, results_message, parse_mode="HTML")
        except Exception:
            pass  # Origin chat might be unavailable
    
    # Kick all players from the game chat
    for player_info in players_info:
        telegram_id = player_info.get('telegram_id')
        if telegram_id:
            try:
                await bot.ban_chat_member(game_chat_id, telegram_id)
                await bot.unban_chat_member(game_chat_id, telegram_id)  # Unban so they can rejoin later
            except Exception:
                pass  # Player might have already left or bot lacks permissions
    
    # Update player pack history with played themes
    pack = await get_pack_by_short_name(game['pack_short_name'])
    if pack:
        for player_uuid in session.players:
            await update_player_pack_history(player_uuid, pack['id'], session.pack_themes)
    
    # Release game chat and delete game
    await release_game_chat(game['id'])
    await delete_game(game_chat_id)


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
            await wait_with_pause(session, 7)
            
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
                await wait_with_pause(session, 1.5)
                
                # Show question
                session.state = GameState.SHOWING_QUESTION
                cost = question.get('cost', (question_idx + 1) * 10)
                question_text = question.get('question', '')
                
                # Get short theme name (without author)
                short_theme_name = theme.get('name', f'Тема {theme_idx + 1}')
                
                # Send the question
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
                
                # Wait for answer (20 seconds)
                session.state = GameState.WAITING_ANSWER
                answered = await wait_for_answer_or_timeout(session, 20.0)
                
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
                    await wait_with_pause(session, 10)
                    
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
        
        # Finalize game: calculate ELO, update stats, kick players, cleanup
        await finalize_game(session, bot)
        
        # Clean up session
        if session.game_chat_id in _active_sessions:
            del _active_sessions[session.game_chat_id]
            
    except asyncio.CancelledError:
        # Game was stopped
        raise
    except Exception as e:
        await bot.send_message(session.game_chat_id, msg_error(str(e)))
        session.state = GameState.IDLE

