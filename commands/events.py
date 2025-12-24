from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import ChatMemberUpdated

from commands import common
from database import players, games, game_chats, packs
from game import session_manager, GameStatus
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
    
    if status == GameStatus.RUNNING.value:
        db_player = await common.ensure_player_exists(user)
        if db_player['id'] in game['players']:
            return
        
        spectators = game.get('spectators') or []
        if db_player['id'] in spectators:
            return
        
        session = session_manager.get(chat_id)
        if session:
            remaining_themes = session.pack_themes[session.current_theme_idx:]
            
            pack = await packs.get_pack_by_short_name(game['pack_short_name'])
            if pack:
                histories = await packs.get_player_pack_histories([db_player['id']])
                player_played_themes: set[int] = set()
                
                for h in histories:
                    if str(h['pack_id']) == str(pack['id']):
                        player_played_themes = packs.parse_themes_played(h['themes_played'])
                        break
                
                has_played_remaining = any(t in player_played_themes for t in remaining_themes)
                
                if has_played_remaining:
                    await games.add_spectator_to_game(game['chat_id'], db_player['id'])
                    session_manager.add_spectator(chat_id, db_player['id'])
                    return
        
        await games.add_player_to_game(game['chat_id'], db_player['id'])
        session_manager.add_player(chat_id, db_player['id'])
        return
    
    if status != GameStatus.STARTING.value:
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
        await games.update_game_status(game['chat_id'], GameStatus.RUNNING)
        await bot.send_message(chat_id, msg_all_players_joined())
        
        origin_chat_id = game.get('origin_chat_id') or game['chat_id']
        await session_manager.start(chat_id, origin_chat_id, bot)
