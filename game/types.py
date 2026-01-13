import asyncio
from enum import Enum
from dataclasses import dataclass
from uuid import UUID


class GameState(Enum):
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
    CORRECT = "correct"
    INCORRECT = "incorrect"
    DOESNT_COUNT = "doesnt_count"
    CONFIRMED_DOESNT_COUNT = "confirmed_doesnt_count"


class GameStatus(Enum):
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    FINISHED = "finished"


@dataclass
class GameSession:
    game_chat_id: int
    origin_chat_id: int

    pack_file: dict
    pack_themes: list[int]

    players: list[UUID]

    state: GameState = GameState.IDLE
    state_before_pause: GameState = GameState.IDLE

    current_theme_idx: int = 0
    current_question_idx: int = 0

    task: asyncio.Task | None = None
    pause_event: asyncio.Event | None = None

    current_question_message_id: int | None = None
    current_question_data: dict | None = None

    answering_player_id: int | None = None
    answer_event: asyncio.Event | None = None
    answer_correct: bool | None = None
    answered_players: dict[int, AnswerState] | None = None
    question_claimed: bool = False

    player_correct_answers: dict[int, int] | None = None
    player_wrong_answers: dict[int, int] | None = None
    player_abs_scores: dict[UUID, int] | None = None
    invite_link: str | None = None
    player_start_theme_idx: dict[UUID, int] | None = None
    timer_extension: float = 0.0
    dispute_poll_id: str | None = None
    dispute_player_id: int | None = None
    dispute_votes: dict[int, bool] | None = None
    disputed_players: set[int] | None = None
    
    kick_poll_id: str | None = None
    kick_player_id: int | None = None
    kick_votes: dict[int, bool] | None = None
    kicked_players: set[int] | None = None
    
    spectators: list[UUID] | None = None
    
    # Partial question display
    partial_display_enabled: bool = False
    current_question_parts: list[str] | None = None
    current_part_index: int = 0
    
    # Pauses per game (per player telegram_id)
    player_pauses: dict[int, int] | None = None

    @classmethod
    def create(
        cls,
        game_chat_id: int,
        origin_chat_id: int,
        pack_file: dict,
        pack_themes: list[int],
        players: list[UUID],
        invite_link: str | None = None,
    ) -> "GameSession":
        pause_event = asyncio.Event()
        pause_event.set()
        
        answer_event = asyncio.Event()
        
        player_start_theme_idx = {player_id: 0 for player_id in players}
        
        return cls(
            game_chat_id=game_chat_id,
            origin_chat_id=origin_chat_id,
            pack_file=pack_file,
            pack_themes=pack_themes,
            players=players,
            pause_event=pause_event,
            answer_event=answer_event,
            player_correct_answers={},
            player_wrong_answers={},
            player_abs_scores={},
            invite_link=invite_link,
            player_start_theme_idx=player_start_theme_idx,
        )

