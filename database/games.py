import json
from uuid import UUID

from database.connection import Database
from game.types import GameStatus


def _parse_jsonb(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


async def create_game(chat_id: int) -> UUID | None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/create_game.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return row['id'] if row else None


async def get_game_by_chat_id(chat_id: int) -> dict | None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_by_chat_id.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def update_game_status(chat_id: int, status: GameStatus) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/update_game_status.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, status.value)


async def add_player_to_game(chat_id: int, player_id: UUID) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/add_player_to_game.sql")
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(sql, chat_id, player_id)


async def add_spectator_to_game(chat_id: int, player_id: UUID) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/add_spectator_to_game.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, player_id)


async def remove_player_from_game(chat_id: int, player_id: UUID) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/remove_player_from_game.sql")
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(sql, chat_id, player_id)


async def delete_game(chat_id: int) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/delete_game.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id)


async def get_game_info(chat_id: int) -> dict | None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_info.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def get_players_with_stats(player_ids: list[UUID]) -> list[dict]:
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_players_with_stats.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


async def cleanup_stale_games() -> list[int]:
    pool = Database.get_pool()
    sql = Database.load_sql("games/cleanup_stale_games.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [row['chat_id'] for row in rows]


async def bulk_update_player_scores(chat_id: int, score_changes: dict[UUID, int]) -> None:
    if not score_changes:
        return
    
    pool = Database.get_pool()
    get_scores_sql = Database.load_sql("games/get_game_scores.sql")
    update_sql = Database.load_sql("games/bulk_update_player_scores.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(get_scores_sql, chat_id)
        if not row:
            return
        
        current_scores = _parse_jsonb(row['scores'])
        
        for player_id, points in score_changes.items():
            player_key = str(player_id)
            current = int(current_scores.get(player_key, 0))
            current_scores[player_key] = current + points
        
        await conn.execute(update_sql, chat_id, json.dumps(current_scores))


async def get_game_scores(chat_id: int) -> dict:
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_scores.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return _parse_jsonb(row['scores']) if row else {}


async def assign_pack_to_game(chat_id: int, pack_short_name: str, pack_themes: list[int]) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/assign_pack_to_game.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, pack_short_name, pack_themes)


async def get_current_position(chat_id: int) -> dict:
    default = {'theme': 0, 'question': 0}
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_current_position.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        if row and row['current_position']:
            pos = _parse_jsonb(row['current_position'])
            return {'theme': int(pos.get('theme', 0)), 'question': int(pos.get('question', 0))}
        return default


async def set_current_position(chat_id: int, theme: int, question: int) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_current_position.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, int(theme), int(question))


async def set_number_of_themes(chat_id: int, number_of_themes: int) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_number_of_themes.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, number_of_themes)


async def set_pack(chat_id: int, pack_short_name: str | None) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_pack.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, pack_short_name)


async def set_game_chat_id(old_chat_id: int, new_chat_id: int) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_game_chat_id.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, old_chat_id, new_chat_id)


async def delete_all_games() -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/delete_all_games.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql)


async def set_invite_link(chat_id: int, invite_link: str) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_invite_link.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, invite_link)


async def set_game_mode(chat_id: int, game_mode: str) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_game_mode.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, game_mode)
