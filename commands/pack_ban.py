import html

from aiogram import Router, types
from aiogram.filters import Command

from database import packs, players

router = Router()


@router.message(Command("ban"))
async def ban_pack_command(message: types.Message) -> None:
    """Ban a pack from random selection for this player."""
    user = message.from_user
    if not user:
        return
    
    # Get command argument (pack short name)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите короткое имя пака.\n"
            "Использование: /ban &lt;short_name&gt;\n"
            "Пример: /ban pack1",
            parse_mode="HTML"
        )
        return
    
    pack_short_name = args[1].strip()
    
    # Get pack by short name
    pack = await packs.get_pack_by_short_name(pack_short_name)
    if not pack:
        await message.answer(f"❌ Пак '{pack_short_name}' не найден.")
        return
    
    # Ensure player exists in database
    db_player = await players.get_player_by_telegram_id(user.id)
    if not db_player:
        from commands.common import ensure_player_exists
        db_player = await ensure_player_exists(user)
    
    # Ban the pack
    result = await packs.ban_pack(user.id, pack['id'])
    
    if result:
        await message.answer(
            f"✅ Пак '{pack['name']}' ({pack_short_name}) забанен.\n"
            f"Он не будет выбираться случайно, но может быть выбран вручную."
        )
    else:
        await message.answer(f"❌ Не удалось забанить пак '{pack_short_name}'.")


@router.message(Command("unban"))
async def unban_pack_command(message: types.Message) -> None:
    """Unban a pack for this player."""
    user = message.from_user
    if not user:
        return
    
    # Get command argument (pack short name)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите короткое имя пака.\n"
            "Использование: /unban &lt;short_name&gt;\n"
            "Пример: /unban pack1",
            parse_mode="HTML"
        )
        return
    
    pack_short_name = args[1].strip()
    
    # Get pack by short name
    pack = await packs.get_pack_by_short_name(pack_short_name)
    if not pack:
        await message.answer(f"❌ Пак '{pack_short_name}' не найден.")
        return
    
    # Unban the pack
    result = await packs.unban_pack(user.id, pack['id'])
    
    if result:
        await message.answer(
            f"✅ Пак '{pack['name']}' ({pack_short_name}) разбанен.\n"
            f"Он снова доступен для случайного выбора."
        )
    else:
        await message.answer(
            f"❌ Пак '{pack_short_name}' не был забанен или не найден."
        )


@router.message(Command("banned_packs"))
async def banned_list_command(message: types.Message) -> None:
    """Show all banned packs for this player or the replied-to player."""
    user = message.from_user
    if not user:
        return

    target_user = user
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    
    # Get all banned packs for the player
    banned = await packs.get_banned_packs(target_user.id)
    
    if not banned:
        target_name = html.escape(target_user.full_name)
        await message.answer(
            f"📋 У пользователя {target_name} нет забаненных паков.",
            parse_mode="HTML"
        )
        return
    
    target_name = html.escape(target_user.full_name)
    short_names = "\n".join(
        f"<code>{html.escape(pack['short_name'])}</code>"
        for pack in banned
    )
    response = (
        f"🚫 <b>Забаненные паки пользователя {target_name}:</b>\n\n"
        f"{short_names}"
    )
    
    await message.answer(response, parse_mode="HTML")
