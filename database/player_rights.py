from database.connection import Database


async def get_player_rights(telegram_id: int) -> dict | None:
    """Get player rights by telegram_id."""
    pool = Database.get_pool()
    sql = Database.load_sql("player_rights/get_player_rights.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None


async def ensure_player_rights(telegram_id: int) -> dict | None:
    """Ensure player has rights record with defaults, return existing or new."""
    pool = Database.get_pool()
    sql = Database.load_sql("player_rights/ensure_player_rights.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None


async def decrement_pauses(telegram_id: int) -> dict | None:
    """Decrement number_of_pauses by 1 for a player. Returns updated record or None if no pauses left."""
    pool = Database.get_pool()
    sql = Database.load_sql("player_rights/decrement_pauses.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None

