from aiogram import types

from database.players import upsert_player
from database.statistics import create_statistics
from database.player_rights import ensure_player_rights
from database import games
from messages import build_game_info_message


async def ensure_player_exists(user: types.User) -> dict:
    player = await upsert_player(user.id, user.username, user.first_name, user.last_name)
    await create_statistics(player['id'])
    await ensure_player_rights(user.id)
    return player


async def send_game_info(message: types.Message, chat_id: int) -> None:
    game_info = await games.get_game_info(chat_id)
    if not game_info:
        await message.answer("Ошибка получения информации об игре.")
        return
    players = await games.get_players_with_stats(game_info['players'])

    await message.answer(
        build_game_info_message(
            pack_name=game_info['pack_name'],
            number_of_themes=game_info['number_of_themes'],
            players=players,
        ),
        parse_mode="HTML"
    )
