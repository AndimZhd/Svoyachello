from aiogram import Bot, Router, types, F
from aiogram.filters import Command

from commands.common import send_game_info
from database import games, game_chats, packs
from database.players import get_player_by_telegram_id
from database.player_rights import ensure_player_rights
from game import session_manager, GameStatus, finalize_game

router = Router()


async def is_spectator(chat_id: int, telegram_id: int) -> bool:
    player = await get_player_by_telegram_id(telegram_id)
    if not player:
        return False
    return session_manager.is_spectator(chat_id, player['id'])


@router.message(Command("themes"))
@router.message(F.text.func(lambda t: t.lower().startswith("темы") if t else False))
async def themes_command(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await message.answer("В этом чате нет активной игры.")
        return
    
    if game['status'] != GameStatus.REGISTERED.value:
        await message.answer("Нельзя изменить настройки после начала игры.")
        return
    
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
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    
    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        await message.answer("В этом чате нет активной игры.")
        return
    
    if game['status'] != GameStatus.REGISTERED.value:
        await message.answer("Нельзя изменить настройки после начала игры.")
        return
    
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
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
    
    pack_short_name = args[1].strip().lower()
    
    random_aliases = ['случайный', 'рандом', 'случ', 'random']
    if pack_short_name in random_aliases:
        await games.set_pack(chat_id, None)
        await message.answer("🎲 Пак будет выбран случайно при старте игры.")
        return
    
    pack = await packs.get_pack_by_short_name(pack_short_name)
    if not pack:
        await message.answer(f"Пак '{pack_short_name}' не найден.")
        return
    
    await games.set_pack(chat_id, pack_short_name)
    await send_game_info(message, chat_id)


@router.message(Command("pack_list"))
@router.message(F.text.lower() == "паки")
async def pack_list_command(message: types.Message) -> None:
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
async def abort_command(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    
    rights = await ensure_player_rights(user.id)
    if rights and not rights['can_abort']:
        return
    
    chat_id = message.chat.id
    
    await finalize_game(chat_id, bot, is_aborted=True)
    
    await message.answer("🛑 Игра отменена.")


@router.message(Command("abort_all"))
async def abort_all_command(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    
    rights = await ensure_player_rights(user.id)
    if not rights or not rights['can_abort_all']:
        return
    
    await session_manager.finalize_all(bot, is_aborted=True)
    
    await message.answer("🗑 Все игры отменены.")


@router.message(Command("kick_player"))
@router.message(F.text.lower() == "кикнуть нахуй")
async def kick_player_command(message: types.Message, bot: Bot) -> None:
    import asyncio
    from commands.answer import apply_kick_result
    
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        return
    
    if await is_spectator(chat_id, user.id):
        return
    
    if session.kick_poll_id is not None:
        await message.answer("Уже идёт голосование по исключению игрока.")
        return
    
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Ответьте на сообщение игрока, которого хотите исключить.")
        return
    
    target = message.reply_to_message.from_user
    
    if target.is_bot:
        return
    
    if session.kicked_players and target.id in session.kicked_players:
        await message.answer("Этот игрок уже исключён.")
        return
    
    target_name = f"{target.first_name or ''} {target.last_name or ''}".strip() or target.username or "Игрок"
    
    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"Исключить игрока {target_name}?",
        options=["✅ Да, исключить", "❌ Нет, оставить"],
        is_anonymous=False,
        allows_multiple_answers=False
    )
    
    if not poll_msg.poll:
        await message.answer("Ошибка создания голосования.")
        return
    
    poll_id = poll_msg.poll.id
    session.kick_poll_id = poll_id
    session.kick_player_id = target.id
    session.kick_votes = {}
    session_manager.register_poll(poll_id, chat_id)
    
    async def auto_apply_kick():
        await asyncio.sleep(10)
        current_session = session_manager.get(chat_id)
        if current_session and current_session.kick_poll_id == poll_id:
            await apply_kick_result(current_session, bot)
    
    asyncio.create_task(auto_apply_kick())


@router.message(Command("partial_display"))
@router.message(F.text.func(lambda t: t and t.lower() in ["постепенный показ", "постепенный показ вопроса", "постепенный показ вопросов"]))
async def partial_display_command(message: types.Message) -> None:
    """Toggle partial question display mode."""
    user = message.from_user
    if not user:
        return
    
    chat_id = message.chat.id
    session = session_manager.get(chat_id)
    
    if not session:
        await message.answer("В этом чате нет активной игры.")
        return
    
    # Toggle the setting
    session.partial_display_enabled = not session.partial_display_enabled
    
    if session.partial_display_enabled:
        await message.answer(
            "✅ Постепенный показ вопросов включён.\n"
            "Длинные вопросы будут отображаться частями."
        )
    else:
        await message.answer(
            "❌ Постепенный показ вопросов отключён.\n"
            "Вопросы будут показываться полностью."
        )
