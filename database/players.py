from uuid import UUID

from database.connection import Database


async def upsert_player(telegram_id: int, username: str | None, first_name: str | None, last_name: str | None) -> dict:
    """Insert or update a player. Returns the player record."""
    pool = Database.get_pool()
    sql = Database.load_sql("players/upsert_player.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id, username, first_name, last_name)
        return dict(row)


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


async def get_players_by_telegram_ids(telegram_ids: list[int]) -> dict[int, dict]:
    """Get players by multiple Telegram IDs. Returns {telegram_id: player_dict}."""
    if not telegram_ids:
        return {}
    
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_players_by_telegram_ids.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, telegram_ids)
        return {row['telegram_id']: dict(row) for row in rows}


