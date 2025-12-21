from uuid import UUID

from database.connection import Database


async def upsert_player(telegram_id: int, username: str | None) -> UUID:
    """Insert or update a player. Returns the player's UUID."""
    pool = Database.get_pool()
    sql = Database.load_sql("players/upsert_player.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id, username)
        return row['id']


async def get_player_by_telegram_id(telegram_id: int) -> dict | None:
    """Get player by Telegram ID."""
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_player_by_telegram_id.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None


async def get_players_telegram_ids(player_ids: list[UUID]) -> list[dict]:
    """Get telegram_ids for a list of player UUIDs."""
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_players_telegram_ids.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


