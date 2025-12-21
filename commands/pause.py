from aiogram import Router, types, F
from aiogram.filters import Command

from database.game_chats import get_game_by_game_chat
from game import pause_game_session, resume_game_session, get_session, GameState

router = Router()


@router.message(Command("pause"))
@router.message(F.text == "пауза")
@router.message(F.text == "стоямба")
async def pause_game(message: types.Message) -> None:
    """Pause the current game."""
    chat_id = message.chat.id
    
    # Check if there's a game session in this chat
    session = get_session(chat_id)
    if not session:
        # Maybe check if this is a game chat
        game = await get_game_by_game_chat(chat_id)
        if not game:
            await message.answer("Нет активной игры в этом чате.")
            return
        await message.answer("Игра не запущена.")
        return
    
    if session.state == GameState.PAUSED:
        return
    
    if pause_game_session(chat_id):
        await message.answer("⏸ Игра приостановлена. Используйте /resume для продолжения.")
    else:
        await message.answer("Не удалось приостановить игру.")


@router.message(Command("resume"))
@router.message(F.text == "продолжить")
@router.message(F.text == "го")
async def resume_game(message: types.Message) -> None:
    """Resume a paused game."""
    chat_id = message.chat.id
    
    # Check if there's a game session in this chat
    session = get_session(chat_id)
    if not session:
        return
    
    if session.state != GameState.PAUSED:
        return
    
    if resume_game_session(chat_id):
        await message.answer("▶️ Игра продолжается!")
    else:
        await message.answer("Не удалось возобновить игру.")

