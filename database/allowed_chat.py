from uuid import UUID

from database.connection import Database


async def get_allowed_chat(chat_id: int) -> dict | None:
    """Get allowed_chat record for a specific chat_id."""
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/get_allowed_chat.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def is_chat_allowed(chat_id: int) -> bool:
    """Check if a chat is allowed to register for games.
    
    If chat is not in the table, it will be automatically added with is_allowed=True.
    Returns True if the chat is explicitly allowed.
    Returns False if the chat is explicitly blocked.
    """
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/is_chat_allowed.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        # If chat not in table, add it with is_allowed=True
        if row is None:
            await upsert_allowed_chat(chat_id, is_allowed=False)
            return False
        return row['is_allowed']


async def upsert_allowed_chat(chat_id: int, is_allowed: bool) -> None:
    """Insert or update allowed_chat record."""
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/upsert_allowed_chat.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, is_allowed)


async def get_all_allowed_chats() -> list[dict]:
    """Get all allowed chats."""
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/get_all_allowed_chats.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [dict(row) for row in rows]


async def get_all_chats() -> list[dict]:
    """Get all chats in the allowed_chat table (both allowed and disallowed)."""
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/get_all_chats.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [dict(row) for row in rows]


async def delete_allowed_chat(chat_id: int) -> None:
    """Delete an allowed_chat record."""
    pool = Database.get_pool()
    sql = Database.load_sql("allowed_chat/delete_allowed_chat.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id)

