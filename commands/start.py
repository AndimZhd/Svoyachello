import random

from aiogram import Bot, Router, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat

from database import games, game_chats, players, packs
from game import GameStatus

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
@router.message(F.text.lower() == "старт")
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

    themes_needed = game['number_of_themes']
    available_packs = await packs.get_available_packs_for_players(game['players'], themes_needed)
    
    if not available_packs:
        await message.answer("Нет доступных паков с достаточным количеством тем для всех игроков.")
        return
    
    selected_pack = random.choice(available_packs)
    
    selected_themes = selected_pack.available_theme_indices[:themes_needed]
    
    await games.assign_pack_to_game(chat_id, selected_pack.short_name, selected_themes)

    game_chat = await game_chats.get_available_game_chat()
    if not game_chat:
        await message.answer("Нет доступных чатов для игры. Попробуйте позже.")
        return

    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=game_chat['chat_id'],
            member_limit=len(game['players']) * 2 + 5
        )
    except Exception as e:
        await message.answer(f"Ошибка создания ссылки: {e}")
        return

    await game_chats.assign_game_to_chat(game_chat['id'], game['id'])
    
    game_chat_id = game_chat['chat_id']
    await games.set_game_chat_id(chat_id, game_chat_id)
    
    await games.set_invite_link(game_chat_id, invite_link.invite_link)
    
    try:
        await bot.set_my_commands(
            GAME_CHAT_COMMANDS,
            scope=BotCommandScopeChat(chat_id=game_chat['chat_id'])
        )
    except Exception:
        pass
    
    await games.update_game_status(game_chat_id, GameStatus.STARTING)

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
