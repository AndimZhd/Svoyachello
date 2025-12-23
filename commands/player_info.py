from aiogram import Router, types, F
from aiogram.filters import Command

from commands.common import ensure_player_exists
from database.statistics import get_player_statistics, get_rating, get_rating_by_chat
from messages import build_stats_message

router = Router()


@router.message(Command("player_info"))
@router.message(F.text.lower() == "статка")
@router.message(F.text.lower() == "статистика")
async def player_info(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
    await ensure_player_exists(user)
    
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    else:
        target_user = user

    if target_user.is_bot:
        await message.answer("Боты не участвуют в игре.")
        return

    row = await get_player_statistics(target_user.id)

    if not row:
        await message.answer(f"Игрок {target_user.first_name} не зарегистрирован.")
        return

    display_name = target_user.first_name or row['username'] or 'Игрок'

    await message.answer(
        build_stats_message(
            display_name=display_name,
            row=row,
        ),
        parse_mode="HTML"
    )


@router.message(Command("rating"))
@router.message(F.text.lower() == "рейт")
async def rating_command(message: types.Message) -> None:
    players = await get_rating()
    
    if not players:
        await message.answer("Рейтинг пуст. Сыграйте хотя бы одну игру!")
        return
    
    lines = ["🏆 <b>Рейтинг игроков:</b>\n"]
    
    for i, p in enumerate(players, 1):
        first = p.get('first_name') or ''
        last = p.get('last_name') or ''
        name = f"{first} {last}".strip() or p.get('username') or 'Игрок'
        elo = p.get('elo_rating', 1000)
        games = p.get('games_played', 0)
        wins = p.get('games_won', 0)
        
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        
        lines.append(f"{medal}{i}. {name} — {elo} ({wins}/{games} побед)")
    
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("chat_rating"))
@router.message(F.text.lower() == "чатрейт")
async def chat_rating_command(message: types.Message) -> None:
    user = message.from_user
    chat_id = message.chat.id
    
    players_list = await get_rating_by_chat(chat_id)
    
    if not players_list:
        await message.answer("В этом чате пока нет отслеживаемых игроков. Игроки добавляются автоматически при использовании команд бота.")
        return
    
    lines = ["🏆 <b>Рейтинг игроков чата:</b>\n"]
    
    for i, p in enumerate(players_list, 1):
        first = p.get('first_name') or ''
        last = p.get('last_name') or ''
        name = f"{first} {last}".strip() or p.get('username') or 'Игрок'
        elo = p.get('elo_rating', 1000)
        games_played = p.get('games_played', 0)
        wins = p.get('games_won', 0)
        
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        
        lines.append(f"{medal}{i}. {name} — {elo} ({wins}/{games_played} побед)")
    
    await message.answer("\n".join(lines), parse_mode="HTML")
