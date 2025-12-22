from aiogram import Router, types, F
from aiogram.filters import Command

from commands import common
from database import games

router = Router()


@router.message(Command("register"))
@router.message(F.text == "++")
@router.message(F.text.lower() == "го")
async def register(message: types.Message) -> None:
    """Register player for the game in current chat."""
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    # Ensure player exists in the system
    db_player = await common.ensure_player_exists(user)

    # Get or create game for this chat
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await games.create_game(chat_id)
        game = await games.get_game_by_chat_id(chat_id)
    
    if not game:
        await message.answer("Ошибка создания игры.")
        return

    # Check if player is already in the game
    if not db_player['id'] in game['players']:
        await games.add_player_to_game(chat_id, db_player['id'])
    
    await common.send_game_info(message, chat_id)


@router.message(Command("unregister"))
@router.message(F.text == "-")
@router.message(F.text.lower() == "не го")
async def unregister(message: types.Message) -> None:
    """Unregister player from the game in current chat."""
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    # Ensure player exists in the system
    db_player = await common.ensure_player_exists(user)

    # Get game for this chat
    game = await games.get_game_by_chat_id(chat_id)
    if not game or db_player['id'] not in game['players']:
        await message.answer("В этом чате нет активной игры.")
        return

    # Remove player from the game
    await games.remove_player_from_game(chat_id, db_player['id'])

    await common.send_game_info(message, chat_id)

