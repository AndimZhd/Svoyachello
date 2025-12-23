from uuid import UUID

from database.connection import Database


async def upsert_player(telegram_id: int, username: str | None, first_name: str | None, last_name: str | None) -> dict:
    pool = Database.get_pool()
    sql = Database.load_sql("players/upsert_player.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id, username, first_name, last_name)
        return dict(row)


async def get_player_by_telegram_id(telegram_id: int) -> dict | None:
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_player_by_telegram_id.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None


async def get_players_telegram_ids(player_ids: list[UUID]) -> list[dict]:
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_players_telegram_ids.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


async def get_players_by_telegram_ids(telegram_ids: list[int]) -> dict[int, dict]:
    if not telegram_ids:
        return {}
    
    pool = Database.get_pool()
    sql = Database.load_sql("players/get_players_by_telegram_ids.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, telegram_ids)
        return {row['telegram_id']: dict(row) for row in rows}


async def track_player_in_chat(player_id: UUID, chat_id: int) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("players/upsert_player_chat.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, player_id, chat_id)
