from uuid import UUID

from database.connection import Database


async def get_available_game_chat() -> dict | None:
    """Get an available game chat (one with no game_id)."""
    pool = Database.get_pool()
    sql = Database.load_sql("game_chats/get_available_game_chat.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql)
        return dict(row) if row else None


async def release_all_game_chats() -> None:
    """Release all game chats (set game_id to NULL)."""
    pool = Database.get_pool()
    sql = Database.load_sql("game_chats/release_all_game_chats.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql)


async def get_game_by_game_chat(chat_id: int) -> dict | None:
    """Get game info by game_chat's chat_id."""
    pool = Database.get_pool()
    sql = Database.load_sql("game_chats/get_game_by_game_chat.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def assign_game_to_chat(game_chat_id: UUID, game_id: UUID) -> None:
    """Assign a game to a game chat."""
    pool = Database.get_pool()
    sql = Database.load_sql("game_chats/assign_game_to_chat.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, game_chat_id, game_id)


async def release_game_chat(game_id: UUID) -> None:
    """Release a game chat (set game_id to NULL)."""
    pool = Database.get_pool()
    sql = Database.load_sql("game_chats/release_game_chat.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, game_id)


