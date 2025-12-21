import asyncio
import os

from dotenv import load_dotenv

# Load environment variables from .env file
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
    """Background task that cleans up stale games every 5 minutes."""
    while True:
        await asyncio.sleep(300)  # 5 minutes
        try:
            chat_ids = await cleanup_stale_games()
            for chat_id in chat_ids:
                try:
                    await bot.send_message(chat_id, msg_game_cancelled_inactivity())
                except Exception:
                    pass  # Chat may be unavailable
            if chat_ids:
                print(f"Cleaned up {len(chat_ids)} stale game(s).")
        except Exception as e:
            print(f"Error cleaning up stale games: {e}")


async def main() -> None:
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    # Initialize database
    await Database.connect()
    print("Database connected.")

    bot = Bot(token=token)

    # Set bot commands for registration chats (groups where games are created)
    registration_commands = [
        BotCommand(command="register", description="Присоединиться к игре"),
        BotCommand(command="unregister", description="Выйти из игры"),
        BotCommand(command="themes", description="Установить количество тем"),
        BotCommand(command="pack", description="Выбрать пак вопросов"),
        BotCommand(command="pack_list", description="Список паков"),
        BotCommand(command="start", description="Начать игру"),
        BotCommand(command="player_info", description="Статистика игрока"),
    ]
    
    # Set bot commands for private chats
    private_commands = [
        BotCommand(command="player_info", description="Статистика игрока"),
    ]
    
    await bot.set_my_commands(registration_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_stale_games_task(bot))

    print("Bot is running... Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        await Database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

