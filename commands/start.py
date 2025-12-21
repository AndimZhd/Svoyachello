import random

from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat

from database.games import get_game_by_chat_id, update_game_status, assign_pack_to_game, set_game_chat_id
from database.game_chats import get_available_game_chat, assign_game_to_chat
from database.players import get_players_telegram_ids
from database.packs import get_available_packs_for_players

# Game chat specific commands
GAME_CHAT_COMMANDS = [
    BotCommand(command="answer", description="Ответить на вопрос"),
    BotCommand(command="yes", description="Подтвердить правильный ответ"),
    BotCommand(command="no", description="Признать неправильный ответ"),
    BotCommand(command="accidentally", description="Пометить ответ как случайный"),
    BotCommand(command="pause", description="Приостановить игру"),
    BotCommand(command="resume", description="Продолжить игру"),
]

router = Router()


@router.message(Command("start"))
@router.message(F.text == "старт")
async def start_game(message: types.Message, bot: Bot) -> None:
    """Start the game - assign a pack and game chat, send invite link and tag players."""
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    # Get game for this chat
    game = await get_game_by_chat_id(chat_id)
    if not game:
        return

    # Check if game has players
    if not game['players']:
        await message.answer("Нет зарегистрированных игроков.")
        return

    # Get available packs for all players
    themes_needed = game['number_of_themes']
    available_packs = await get_available_packs_for_players(game['players'], themes_needed)
    
    if not available_packs:
        await message.answer("Нет доступных паков с достаточным количеством тем для всех игроков.")
        return
    
    # Pick a random pack from available ones
    selected_pack = random.choice(available_packs)
    
    # Select random themes from available ones
    selected_themes = selected_pack.available_theme_indices[:themes_needed]
    #selected_themes.sort()
    
    # Assign pack and themes to game
    await assign_pack_to_game(chat_id, selected_pack.short_name, selected_themes)

    # Get an available game chat
    game_chat = await get_available_game_chat()
    if not game_chat:
        await message.answer("Нет доступных чатов для игры. Попробуйте позже.")
        return

    # Create invite link for the game chat
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=game_chat['chat_id'],
            member_limit=len(game['players']) * 2 + 5  # Extra buffer for retries
        )
    except Exception as e:
        await message.answer(f"Ошибка создания ссылки: {e}")
        return

    # Assign game to the chat
    await assign_game_to_chat(game_chat['id'], game['id'])
    
    # Transfer game to game chat
    game_chat_id = game_chat['chat_id']
    await set_game_chat_id(chat_id, game_chat_id)
    
    # Set game-specific commands for the game chat
    try:
        await bot.set_my_commands(
            GAME_CHAT_COMMANDS,
            scope=BotCommandScopeChat(chat_id=game_chat['chat_id'])
        )
    except Exception:
        pass  # Commands may fail if bot doesn't have permission
    
    # Update game status
    await update_game_status(game_chat_id, 'starting')

    # Get player telegram_ids for tagging
    players_info = await get_players_telegram_ids(game['players'])
    
    # Build player mentions
    mentions = []
    for p in players_info:
        if p['username']:
            mentions.append(f"@{p['username']}")
        else:
            mentions.append(f'<a href="tg://user?id={p["telegram_id"]}">Игрок</a>')
    
    players_text = ", ".join(mentions)
    
    await message.answer(
        f"🎮 Игра начинается!\n\n"
        f"📦 Пак: {selected_pack.short_name}\n"
        f"Игроки: {players_text}\n\n"
        f"Присоединяйтесь: {invite_link.invite_link}",
        parse_mode="HTML"
    )


