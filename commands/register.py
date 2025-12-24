from aiogram import Router, types, F
from aiogram.filters import Command

from commands import common
from database import games, game_chats
from game import GameStatus

router = Router()


@router.message(Command("register"))
@router.message(F.text == "++")
@router.message(F.text.lower() == "го")
async def register(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    if await game_chats.get_game_by_game_chat(chat_id):
        return

    db_player = await common.ensure_player_exists(user)

    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await games.create_game(chat_id)
        game = await games.get_game_by_chat_id(chat_id)
    
    if not game:
        await message.answer("Ошибка создания игры.")
        return
    
    if game['status'] != GameStatus.REGISTERED.value:
        return

    if not db_player['id'] in game['players']:
        await games.add_player_to_game(chat_id, db_player['id'])
    
    await common.send_game_info(message, chat_id)


@router.message(Command("unregister"))
@router.message(F.text == "-")
@router.message(F.text.lower() == "не го")
async def unregister(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    db_player = await common.ensure_player_exists(user)

    game = await games.get_game_by_chat_id(chat_id)
    if not game or db_player['id'] not in game['players']:
        return
    
    if game['status'] != GameStatus.REGISTERED.value:
        return

    await games.remove_player_from_game(chat_id, db_player['id'])

    await common.send_game_info(message, chat_id)
