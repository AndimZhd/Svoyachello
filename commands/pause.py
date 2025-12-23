from aiogram import Router, types, F
from aiogram.filters import Command

from database.game_chats import get_game_by_game_chat
from game import session_manager, GameState

router = Router()


@router.message(Command("pause"))
@router.message(F.text.lower() == "пауза")
@router.message(F.text.lower() == "стоямба")
async def pause_game(message: types.Message) -> None:
    chat_id = message.chat.id
    
    session = session_manager.get(chat_id)
    if not session:
        game = await get_game_by_game_chat(chat_id)
        if not game:
            await message.answer("Нет активной игры в этом чате.")
            return
        await message.answer("Игра не запущена.")
        return
    
    if session.state == GameState.PAUSED:
        return
    
    if session.state in (GameState.SHOWING_QUESTION, GameState.WAITING_ANSWER, GameState.PLAYER_ANSWERING):
        await message.answer("Нельзя поставить на паузу во время вопроса.")
        return
    
    if session_manager.pause(chat_id):
        await message.answer("⏸ Игра приостановлена. Используйте /resume для продолжения.")
    else:
        await message.answer("Не удалось приостановить игру.")


@router.message(Command("resume"))
@router.message(F.text.lower() == "продолжить")
async def resume_game(message: types.Message) -> None:
    chat_id = message.chat.id
    
    session = session_manager.get(chat_id)
    if not session:
        return
    
    if session.state != GameState.PAUSED:
        return
    
    if session_manager.resume(chat_id):
        await message.answer("▶️ Игра продолжается!")
    else:
        await message.answer("Не удалось возобновить игру.")
