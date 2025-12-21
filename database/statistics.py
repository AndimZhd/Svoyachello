from uuid import UUID

from database.connection import Database


async def create_statistics(player_id: UUID) -> None:
    """Create statistics record for a player (if not exists)."""
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/create_statistics.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, player_id)


async def get_player_statistics(telegram_id: int) -> dict | None:
    """Get player statistics by Telegram ID."""
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/get_user_statistics.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None

