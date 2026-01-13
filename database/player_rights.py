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


async def get_player_pauses_bulk(telegram_ids: list[int]) -> dict[int, int]:
    """Get number_of_pauses for multiple players. Returns dict of telegram_id -> pauses."""
    if not telegram_ids:
        return {}
    
    pool = Database.get_pool()
    sql = Database.load_sql("player_rights/get_player_pauses_bulk.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, telegram_ids)
        return {row['telegram_id']: row['number_of_pauses'] for row in rows}


async def decrement_pauses(telegram_id: int) -> dict | None:
    """Decrement number_of_pauses by 1 for a player. Returns updated record or None if no pauses left."""
    pool = Database.get_pool()
    sql = Database.load_sql("player_rights/decrement_pauses.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None

