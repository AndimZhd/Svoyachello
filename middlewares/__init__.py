from functools import wraps
from typing import Callable, Any

from aiogram.types import Message

from database.allowed_chat import is_chat_allowed
from database.game_chats import get_game_by_game_chat

__all__ = ["require_allowed_chat", "require_not_game_chat"]


def require_allowed_chat(handler: Callable) -> Callable:
    """Decorator to check if a chat is allowed to use the bot commands.
    
    Only applies to group/supergroup chats. Private chats are always allowed.
    If chat is not allowed, sends access denied message and blocks command execution.
    """
    @wraps(handler)
    async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
        # Only check for group/supergroup chats, allow private chats
        if message.chat.type in ["group", "supergroup"]:
            chat_id = message.chat.id
            
            # Check if chat is allowed
            if not await is_chat_allowed(chat_id):
                # Send access denied message
                await message.answer(
                    "Обратитесь к @AndimZhd для получения доступа"
                )
                return  # Don't process the command
        
        # If chat is allowed or it's a private chat, proceed with the handler
        return await handler(message, *args, **kwargs)
    
    return wrapper


def require_not_game_chat(handler: Callable) -> Callable:
    """Decorator to prevent registration commands from being used in game chats.
    
    Game chats are dedicated chats where the actual game is played.
    Registration commands should only be used in the origin chat.
    """
    @wraps(handler)
    async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
        chat_id = message.chat.id
        
        # Check if this is a game chat
        if await get_game_by_game_chat(chat_id):
            # This is a game chat, don't allow registration commands
            return  # Silently ignore the command
        
        # Not a game chat, proceed with the handler
        return await handler(message, *args, **kwargs)
    
    return wrapper

