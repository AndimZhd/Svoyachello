import asyncio
from uuid import UUID

from aiogram import Bot

from database import games, packs, game_chats
import messages
from .types import GameState, GameSession


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[int, GameSession] = {}
        self._poll_to_chat: dict[str, int] = {}
    
    def register_poll(self, poll_id: str, chat_id: int) -> None:
        self._poll_to_chat[poll_id] = chat_id
    
    def unregister_poll(self, poll_id: str) -> None:
        self._poll_to_chat.pop(poll_id, None)
    
    def get_chat_by_poll(self, poll_id: str) -> int | None:
        return self._poll_to_chat.get(poll_id)
    
    async def start(self, game_chat_id: int, origin_chat_id: int, bot: Bot) -> None:
        if game_chat_id in self._sessions:
            return
        
        game = await games.get_game_by_chat_id(game_chat_id)
        if not game:
            return
        
        pack = await packs.get_pack_by_short_name(game['pack_short_name'])
        if not pack:
            await bot.send_message(game_chat_id, messages.msg_pack_not_found())
            return
        
        session = GameSession.create(
            game_chat_id=game_chat_id,
            origin_chat_id=origin_chat_id,
            pack_file=pack['pack_file'],
            pack_themes=game['pack_themes'],
            players=game['players'],
            invite_link=game.get('invite_link'),
        )

        self._sessions[game_chat_id] = session
        
        if game.get('game_mode') == 'private' and game.get('invite_link'):
            try:
                await bot.revoke_chat_invite_link(game_chat_id, game['invite_link'])
            except Exception:
                pass
        
        from .game_loop import game_loop
        session.task = asyncio.create_task(game_loop(session, bot))
    
    async def stop(self, game_chat_id: int) -> None:
        session = self._sessions.get(game_chat_id)
        if session and session.task:
            session.task.cancel()
            try:
                await session.task
            except asyncio.CancelledError:
                pass
        
        self.remove(game_chat_id)
    
    def stop_all(self) -> None:
        for session in self._sessions.values():
            if session.task:
                session.task.cancel()
        self._sessions.clear()
    
    async def finalize_all(self, bot: Bot, is_aborted: bool = False) -> None:
        from .end_game import finalize_game
        
        chat_ids = list(self._sessions.keys())
        
        for chat_id in chat_ids:
            try:
                await finalize_game(chat_id, bot, is_aborted=is_aborted)
            except Exception:
                pass
        
        await game_chats.release_all_game_chats()
        await games.delete_all_games()
    
    def get(self, game_chat_id: int) -> GameSession | None:
        return self._sessions.get(game_chat_id)
    
    def get_all(self) -> dict[int, GameSession]:
        return self._sessions
    
    def add_player(self, game_chat_id: int, player_id: UUID) -> bool:
        session = self._sessions.get(game_chat_id)
        if not session:
            return False
        
        if player_id in session.players:
            return False
        
        session.players.append(player_id)
        
        if session.player_start_theme_idx is not None:
            session.player_start_theme_idx[player_id] = session.current_theme_idx
        
        return True
    
    def add_spectator(self, game_chat_id: int, player_id: UUID) -> bool:
        session = self._sessions.get(game_chat_id)
        if not session:
            return False
        
        if session.spectators is None:
            session.spectators = []
        
        if player_id in session.spectators:
            return False
        
        session.spectators.append(player_id)
        
        if session.player_start_theme_idx is not None:
            session.player_start_theme_idx[player_id] = session.current_theme_idx
        
        return True
    
    def is_spectator(self, game_chat_id: int, player_id: UUID) -> bool:
        session = self._sessions.get(game_chat_id)
        if not session or not session.spectators:
            return False
        return player_id in session.spectators
    
    def pause(self, game_chat_id: int) -> bool:
        session = self._sessions.get(game_chat_id)
        if not session or not session.pause_event:
            return False
        
        if session.state == GameState.PAUSED:
            return False
        
        if session.state in (GameState.SHOWING_QUESTION, GameState.WAITING_ANSWER, GameState.PLAYER_ANSWERING):
            return False
        
        session.state_before_pause = session.state
        session.state = GameState.PAUSED
        session.pause_event.clear()
        return True
    
    def resume(self, game_chat_id: int) -> bool:
        session = self._sessions.get(game_chat_id)
        if not session or not session.pause_event:
            return False
        
        if session.state != GameState.PAUSED:
            return False
        
        session.state = session.state_before_pause
        session.pause_event.set()
        return True
    
    def remove(self, game_chat_id: int) -> None:
        if game_chat_id in self._sessions:
            del self._sessions[game_chat_id]


session_manager = SessionManager()
