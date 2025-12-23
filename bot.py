import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from database import Database
from database.games import cleanup_stale_games
from commands import router as commands_router
from messages import msg_game_cancelled_inactivity


dp = Dispatcher()
dp.include_router(commands_router)


async def cleanup_stale_games_task(bot: Bot) -> None:
    while True:
        await asyncio.sleep(300)
        try:
            chat_ids = await cleanup_stale_games()
            for chat_id in chat_ids:
                try:
                    await bot.send_message(chat_id, msg_game_cancelled_inactivity())
                except Exception:
                    pass
        except Exception:
            pass


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    await Database.connect()

    bot = Bot(token=token)

    registration_commands = [
        BotCommand(command="register", description="Присоединиться к игре"),
        BotCommand(command="unregister", description="Выйти из игры"),
        BotCommand(command="themes", description="Установить количество тем"),
        BotCommand(command="pack", description="Выбрать пак вопросов"),
        BotCommand(command="pack_list", description="Список паков"),
        BotCommand(command="make_private", description="Сделать игру приватной"),
        BotCommand(command="start", description="Начать игру"),
        BotCommand(command="player_info", description="Статистика игрока"),
        BotCommand(command="rating", description="Рейтинг игроков"),
        BotCommand(command="chat_rating", description="Рейтинг игроков чата"),
    ]
    
    private_commands = [
        BotCommand(command="player_info", description="Статистика игрока"),
        BotCommand(command="rating", description="Рейтинг игроков"),
    ]
    
    await bot.set_my_commands(registration_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    cleanup_task = asyncio.create_task(cleanup_stale_games_task(bot))

    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        await Database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
