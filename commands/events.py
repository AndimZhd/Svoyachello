from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import ChatMemberUpdated

from database import players, games, game_chats
from game import start_game_session
from messages import msg_all_players_joined

router = Router()


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_player_joined(event: ChatMemberUpdated, bot: Bot) -> None:
    """Handle when a player joins the game chat."""
    chat_id = event.chat.id
    user = event.new_chat_member.user
    
    # Ignore bots
    if user.is_bot:
        return
    
    # Get the game associated with this chat
    game = await game_chats.get_game_by_game_chat(chat_id)
    if not game or game['status'] != 'starting':
        return
    
    # Get player info
    db_player = await players.get_player_by_telegram_id(user.id)
    if not db_player or db_player['id'] not in game['players']:
        return  # Not a player of this game
    
    # Get all players' telegram_ids
    players_info = await players.get_players_telegram_ids(game['players'])
    player_telegram_ids = {p['telegram_id'] for p in players_info}
    
    # Check which players are in the chat
    joined_count = 0
    for telegram_id in player_telegram_ids:
        try:
            member = await bot.get_chat_member(chat_id, telegram_id)
            if member.status in ('member', 'administrator', 'creator'):
                joined_count += 1
        except Exception:
            pass  # User not in chat or error
    
    # If all players joined, start the game
    if joined_count == len(game['players']):
        await games.update_game_status(game['chat_id'], 'running')
        await bot.send_message(chat_id, msg_all_players_joined())
        
        # Start the game state machine
        await start_game_session(chat_id, game['chat_id'], bot)


