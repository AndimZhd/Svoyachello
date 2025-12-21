from aiogram import Router, types, F
from aiogram.filters import Command

from commands.common import send_game_info
from database.games import get_game_by_chat_id, set_number_of_themes, set_pack, delete_all_games
from database.game_chats import release_all_game_chats
from database.packs import get_pack_by_short_name, get_all_packs
from game import stop_all_sessions

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
    game = await get_game_by_chat_id(chat_id)
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
    
    await set_number_of_themes(chat_id, num)
    await send_game_info(message, chat_id)


@router.message(Command("pack"))
@router.message(F.text.func(lambda t: t.lower().startswith("пак") if t else False))
async def pack_command(message: types.Message) -> None:
    """Set pack for the current game."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    # Get game for this chat
    game = await get_game_by_chat_id(chat_id)
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
        packs = await get_all_packs()
        if not packs:
            await message.answer("Нет доступных паков.")
            return
        
        pack_list = "\n".join([f"• {p['short_name']} - {p['name']}" for p in packs])
        current = game['pack_short_name'] or "не выбран"
        await message.answer(
            f"Текущий пак: {current}\n\n"
            f"Доступные паки:\n{pack_list}\n\n"
            f"Использование: /pack <short_name>"
        )
        return
    
    pack_short_name = args[1].strip()
    
    # Validate pack exists
    pack = await get_pack_by_short_name(pack_short_name)
    if not pack:
        await message.answer(f"Пак '{pack_short_name}' не найден.")
        return
    
    await set_pack(chat_id, pack_short_name)
    await send_game_info(message, chat_id)


@router.message(Command("pack_list"))
@router.message(F.text == "паки")
async def pack_list_command(message: types.Message) -> None:
    """Show list of all available packs."""
    packs = await get_all_packs()
    
    if not packs:
        await message.answer("Нет доступных паков.")
        return
    
    pack_lines = []
    for p in packs:
        pack_lines.append(f"<b>{p['short_name']}</b> — {p['name']} ({p['number_of_themes']} тем)")
    
    await message.answer(
        "📦 <b>Доступные паки:</b>\n\n" + "\n".join(pack_lines),
        parse_mode="HTML"
    )


@router.message(Command("abort_all"))
async def abort_all_command(message: types.Message) -> None:
    """Delete all games and release all game chats."""
    # Stop all active game sessions
    stop_all_sessions()
    
    # Release all game chats
    await release_all_game_chats()
    
    # Delete all games
    await delete_all_games()
    
    await message.answer("🗑 Все игры удалены, все игровые чаты освобождены.")