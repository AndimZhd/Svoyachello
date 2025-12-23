from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import ChatMemberUpdated

from commands import common
from database import players, games, game_chats
from game import session_manager
from messages import msg_all_players_joined

router = Router()


async def kick_player(bot: Bot, chat_id: int, user_id: int) -> None:
    try:
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)
    except Exception:
        pass


async def is_registered_player(user_id: int, game_players: list) -> bool:
    db_player = await players.get_player_by_telegram_id(user_id)
    return db_player is not None and db_player['id'] in game_players


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_player_joined(event: ChatMemberUpdated, bot: Bot) -> None:
    chat_id = event.chat.id
    user = event.new_chat_member.user
    
    if user.is_bot:
        return
    
    game = await game_chats.get_game_by_game_chat(chat_id)
    if not game:
        return
    
    is_private = game.get('game_mode') == 'private'
    status = game['status']
    
    if is_private:
        if not await is_registered_player(user.id, game['players']):
            await kick_player(bot, chat_id, user.id)
            return
    
    if status == 'running':
        db_player = await common.ensure_player_exists(user)
        if db_player['id'] not in game['players']:
            await games.add_player_to_game(game['chat_id'], db_player['id'])
            session_manager.add_player(chat_id, db_player['id'])
        return
    
    if status != 'starting':
        return
    
    db_player = await common.ensure_player_exists(user)
    if db_player['id'] not in game['players']:
        await games.add_player_to_game(game['chat_id'], db_player['id'])
        game = await game_chats.get_game_by_game_chat(chat_id)
        if not game:
            return
    
    players_info = await players.get_players_telegram_ids(game['players'])
    player_telegram_ids = {p['telegram_id'] for p in players_info}
    
    joined_count = 0
    for telegram_id in player_telegram_ids:
        try:
            member = await bot.get_chat_member(chat_id, telegram_id)
            if member.status in ('member', 'administrator', 'creator'):
                joined_count += 1
        except Exception:
            pass
    
    if joined_count == len(game['players']):
        await games.update_game_status(game['chat_id'], 'running')
        await bot.send_message(chat_id, msg_all_players_joined())
        
        origin_chat_id = game.get('origin_chat_id') or game['chat_id']
        await session_manager.start(chat_id, origin_chat_id, bot)
