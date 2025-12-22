from aiogram import Router, types, F
from aiogram.filters import Command

from commands.common import send_game_info
from database import games, game_chats, packs
from game import stop_all_sessions, stop_game_session

router = Router()


@router.message(Command("themes"))
@router.message(F.text.func(lambda t: t.lower().startswith("темы") if t else False))
async def themes_command(message: types.Message) -> None:
    """Set number of themes for the current game."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    # Get game for this chat
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await message.answer("В этом чате нет активной игры.")
        return
    
    # Check if game is in registered status
    if game['status'] != 'registered':
        await message.answer("Нельзя изменить настройки после начала игры.")
        return
    
    # Parse argument
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
        await message.answer(
            f"Текущее количество тем: {game['number_of_themes']}\n"
            f"Использование: /themes <число>"
        )
        return
    
    try:
        num = int(args[1])
        if num < 1 or num > 20:
            await message.answer("Количество тем должно быть от 1 до 20.")
            return
    except ValueError:
        await message.answer("Укажите число.")
        return
    
    await games.set_number_of_themes(chat_id, num)
    await send_game_info(message, chat_id)


@router.message(Command("pack"))
@router.message(F.text.func(lambda t: t.lower().startswith("пак ") if t else False))
async def pack_command(message: types.Message) -> None:
    """Set pack for the current game."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    # Get game for this chat
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await message.answer("В этом чате нет активной игры.")
        return
    
    # Check if game is in registered status
    if game['status'] != 'registered':
        await message.answer("Нельзя изменить настройки после начала игры.")
        return
    
    # Parse argument
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
        # Show available packs
        all_packs = await packs.get_all_packs()
        if not all_packs:
            await message.answer("Нет доступных паков.")
            return
        
        pack_list = "\n".join([f"• {p['short_name']} - {p['name']}" for p in all_packs])
        current = game['pack_short_name'] or "не выбран"
        await message.answer(
            f"Текущий пак: {current}\n\n"
            f"Доступные паки:\n{pack_list}\n\n"
            f"Использование: /pack <short_name>"
        )
        return
    
    pack_short_name = args[1].strip()
    
    # Validate pack exists
    pack = await packs.get_pack_by_short_name(pack_short_name)
    if not pack:
        await message.answer(f"Пак '{pack_short_name}' не найден.")
        return
    
    await games.set_pack(chat_id, pack_short_name)
    await send_game_info(message, chat_id)


@router.message(Command("pack_list"))
@router.message(F.text.lower() == "паки ")
async def pack_list_command(message: types.Message) -> None:
    """Show list of all available packs."""
    all_packs = await packs.get_all_packs()
    
    if not all_packs:
        await message.answer("Нет доступных паков.")
        return
    
    pack_lines = []
    for p in all_packs:
        pack_lines.append(f"<b>{p['short_name']}</b> — {p['name']} ({p['number_of_themes']} тем)")
    
    await message.answer(
        "📦 <b>Доступные паки:</b>\n\n" + "\n".join(pack_lines),
        parse_mode="HTML"
    )


@router.message(Command("abort"))
async def abort_command(message: types.Message) -> None:
    """End the current game in this chat."""
    chat_id = message.chat.id
    
    # Check if this is a game chat with a running game
    game = await game_chats.get_game_by_game_chat(chat_id)
    
    # If not a game chat, check if it's a registration chat
    if not game:
        game = await games.get_game_by_chat_id(chat_id)
    
    if not game:
        await message.answer("В этом чате нет активной игры.")
        return
    
    # Stop the game session if running
    await stop_game_session(chat_id)
    
    # Release the game chat
    await game_chats.release_game_chat(game['id'])
    
    # Delete the game
    await games.delete_game(game['chat_id'])
    
    await message.answer("🛑 Игра отменена.")


@router.message(Command("abort_all"))
async def abort_all_command(message: types.Message) -> None:
    """Delete all games and release all game chats."""
    # Stop all active game sessions
    stop_all_sessions()
    
    # Release all game chats
    await game_chats.release_all_game_chats()
    
    # Delete all games
    await games.delete_all_games()
    
    await message.answer("🗑 Все игры удалены, все игровые чаты освобождены.")