import random

from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat

from database import games, game_chats, players, packs
from game import GameStatus
from middlewares import require_allowed_chat, require_not_game_chat

GAME_CHAT_COMMANDS = [
    BotCommand(command="answer", description="Ответить на вопрос"),
    BotCommand(command="yes", description="Подтвердить правильный ответ"),
    BotCommand(command="no", description="Признать неправильный ответ"),
    BotCommand(command="accidentally", description="Пометить ответ как случайный"),
    BotCommand(command="dispute", description="Оспорить ответ игрока"),
    BotCommand(command="correct", description="Исправить счёт"),
    BotCommand(command="pause", description="Приостановить игру"),
    BotCommand(command="resume", description="Продолжить игру"),
    BotCommand(command="kick_player", description="Исключить игрока голосованием"),
    BotCommand(command="partial_display", description="Переключить показ вопроса"),
    BotCommand(command="skip_theme", description="Пропустить текущую тему"),
    BotCommand(command="abort", description="Отменить текущую игру"),
]

router = Router()


@router.message(Command("start"))
@router.message(F.text.lower() == "старт")
@require_not_game_chat
@require_allowed_chat
async def start_game(message: types.Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return
    chat_id = message.chat.id

    game = await games.get_game_by_chat_id(chat_id)
    if not game:
        return
    
    if game['status'] != GameStatus.REGISTERED.value:
        return

    if not game['players']:
        await message.answer("Нет зарегистрированных игроков.")
        return
    
    # Update status to STARTING immediately to prevent race condition
    await games.update_game_status(chat_id, GameStatus.STARTING)
    
    # Refresh game data to ensure we have the latest status
    game = await games.get_game_by_chat_id(chat_id)
    if not game or game['status'] != GameStatus.STARTING.value:
        # Another process already started the game
        return

    themes_needed = game['number_of_themes']
    selected_pack = None
    
    # Check if a pack was pre-selected
    if game['pack_short_name']:
        # Try to use the pre-selected pack (ignores bans for manual selection)
        selected_pack = await packs.check_pack_for_manual_selection(
            game['pack_short_name'],
            game['players'],
            themes_needed
        )
        
        if not selected_pack:
            # Revert status back to REGISTERED on error
            await games.update_game_status(chat_id, GameStatus.REGISTERED)
            
            # Check if pack exists at all
            pack_exists = await packs.get_pack_by_short_name(game['pack_short_name'])
            if not pack_exists:
                await message.answer(
                    f"❌ Пак '{game['pack_short_name']}' не найден.\n"
                )
            else:
                await message.answer(
                    f"❌ Пак '{game['pack_short_name']}' не имеет достаточно непройденных тем для всех игроков.\n"
                    f"Выберите другой пак с помощью /pack или сбросьте выбор командой /pack случайный"
                )
            return
        
        selected_themes = selected_pack.available_theme_indices[:themes_needed]
        await games.assign_pack_to_game(chat_id, selected_pack.short_name, selected_themes)
    else:
        # No pack was pre-selected, choose randomly
        available_packs = await packs.get_available_packs_for_players(game['players'], themes_needed)
        
        if not available_packs:
            # Revert status back to REGISTERED on error
            await games.update_game_status(chat_id, GameStatus.REGISTERED)
            await message.answer("Нет доступных паков с достаточным количеством тем для всех игроков.")
            return
        
        selected_pack = random.choice(available_packs)
        
        selected_themes = selected_pack.available_theme_indices[:themes_needed]
        
        await games.assign_pack_to_game(chat_id, selected_pack.short_name, selected_themes)

    game_chat = await game_chats.get_available_game_chat()
    if not game_chat:
        # Revert status back to REGISTERED on error
        await games.update_game_status(chat_id, GameStatus.REGISTERED)
        await message.answer("Нет доступных чатов для игры. Попробуйте позже.")
        return

    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=game_chat['chat_id'],
            member_limit=len(game['players']) * 2 + 5
        )
    except Exception as e:
        # Revert status back to REGISTERED on error
        await games.update_game_status(chat_id, GameStatus.REGISTERED)
        await message.answer(f"Ошибка создания ссылки: {e}")
        return

    try:
        await game_chats.assign_game_to_chat(game_chat['id'], game['id'])
        
        game_chat_id = game_chat['chat_id']
        await games.set_game_chat_id(chat_id, game_chat_id)
        
        await games.set_invite_link(game_chat_id, invite_link.invite_link)
    except Exception as e:
        # Race condition: another game already took this chat or game
        # Revert status and notify user
        await games.update_game_status(chat_id, GameStatus.REGISTERED)
        await game_chats.release_game_chat(game['id'])
        await message.answer("Ошибка при назначении чата. Попробуйте еще раз.")
        return
    
    try:
        await bot.set_my_commands(
            GAME_CHAT_COMMANDS,
            scope=BotCommandScopeChat(chat_id=game_chat['chat_id'])
        )
    except Exception:
        pass
    
    # Keep status as STARTING (already set at the beginning)
    # It will be updated to RUNNING when the game loop starts

    players_info = await players.get_players_telegram_ids(game['players'])
    
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
