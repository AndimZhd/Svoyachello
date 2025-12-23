from aiogram import Router, types, F
from aiogram.filters import Command

from database import games

router = Router()


@router.message(Command("make_private"))
@router.message(F.text.lower() == "приватизировать")
async def make_private(message: types.Message) -> None:
    chat_id = message.chat.id
    
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        return
    
    if game['status'] != 'registered':
        await message.answer("Нельзя изменить режим игры после её начала.")
        return
    
    if game.get('game_mode') == 'private':
        await message.answer("Игра уже в приватном режиме.")
        return
    
    await games.set_game_mode(chat_id, 'private')
    await message.answer("🔒 Игра переведена в приватный режим. Новые игроки не смогут присоединиться после старта.")


@router.message(Command("make_public"))
@router.message(F.text.lower() == "деприватизировать")
async def make_public(message: types.Message) -> None:
    chat_id = message.chat.id
    
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        return
    
    if game['status'] != 'registered':
        await message.answer("Нельзя изменить режим игры после её начала.")
        return
    
    if game.get('game_mode', 'public') == 'public':
        await message.answer("Игра уже в публичном режиме.")
        return
    
    await games.set_game_mode(chat_id, 'public')
    await message.answer("🔓 Игра переведена в публичный режим. Новые игроки смогут присоединиться после старта.")
