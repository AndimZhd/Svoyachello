from aiogram import types

from database.players import upsert_player
from database.statistics import create_statistics
from database.games import get_game_info, get_players_with_stats
from messages import build_game_info_message


async def ensure_player_exists(user: types.User) -> dict:
    """Ensure player exists in database, create if not. Returns player dict."""
    player = await upsert_player(user.id, user.username, user.first_name, user.last_name)
    # Ensure statistics exist for this player
    await create_statistics(player['id'])
    return player


async def send_game_info(message: types.Message, chat_id: int) -> None:
    """Get game info and send it to the chat."""
    game_info = await get_game_info(chat_id)
    if not game_info:
        await message.answer("Ошибка получения информации об игре.")
        return
    players = await get_players_with_stats(game_info['players'])

    await message.answer(
        build_game_info_message(
            pack_name=game_info['pack_name'],
            number_of_themes=game_info['number_of_themes'],
            players=players,
        ),
        parse_mode="HTML"
    )


