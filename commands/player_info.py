from aiogram import Router, types
from aiogram.filters import Command

from commands.common import ensure_player_exists
from database.statistics import get_player_statistics
from messages import build_stats_message

router = Router()


@router.message(Command("player_info"))
async def player_info(message: types.Message) -> None:
    """Show user stats. Reply to a message to see that player's stats."""
    user = message.from_user
    if not user:
        return
    
    # Ensure the command sender exists in the system
    await ensure_player_exists(user)
    
    # Check if replying to another user's message
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    else:
        target_user = user

    # Don't show stats for bots
    if target_user.is_bot:
        await message.answer("Боты не участвуют в игре.")
        return

    row = await get_player_statistics(target_user.id)

    if not row:
        await message.answer(f"Игрок {target_user.first_name} не зарегистрирован.")
        return

    # Get display name (from Telegram, fallback to username)
    display_name = target_user.first_name or row['username'] or 'Игрок'

    await message.answer(
        build_stats_message(
            display_name=display_name,
            row=row,
        ),
        parse_mode="HTML"
    )


