from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from database.game_chats import get_game_by_game_chat
from database.player_rights import ensure_player_rights
from game import session_manager, GameState

router = Router()


@router.message(Command("pause"))
@router.message(F.text.lower() == "пауза")
@router.message(F.text.lower() == "стоямба")
async def pause_game(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    
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
    
    # Check pauses from session (per-game pauses)
    if session.player_pauses is None:
        session.player_pauses = {}
    
    pauses_left = session.player_pauses.get(user.id, 5)  # Default to 5 if not found
    
    if pauses_left <= 0:
        await message.answer("Пошёл нахуй")
        return
    
    if session_manager.pause(chat_id):
        # Decrement pauses in session only
        session.player_pauses[user.id] = pauses_left - 1
        
        # Create keyboard with продолжить, да, нет, случ
        pause_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="продолжить"),
                    KeyboardButton(text="да"),
                    KeyboardButton(text="нет"),
                    KeyboardButton(text="случ")
                ]
            ],
            resize_keyboard=False,
            one_time_keyboard=False
        )
        
        await message.answer("⏸ Игра приостановлена. Используйте /resume для продолжения.", reply_markup=pause_keyboard)
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
        # Create keyboard with да, нет, случ, пауза
        resume_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="да"),
                    KeyboardButton(text="нет"),
                    KeyboardButton(text="случ"),
                    KeyboardButton(text="пауза")
                ]
            ],
            resize_keyboard=False,
            one_time_keyboard=False
        )

        await message.answer("▶️ Игра продолжается!", reply_markup=resume_keyboard)
    else:
        await message.answer("Не удалось возобновить игру.")
