import json
from uuid import UUID

from database.connection import Database


def _parse_jsonb(value) -> dict:
    """Parse JSONB value that might be dict or string."""
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
    """Create a new game for a chat. Returns game UUID or None if already exists."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/create_game.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return row['id'] if row else None


async def get_game_by_chat_id(chat_id: int) -> dict | None:
    """Get game by chat ID."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_by_chat_id.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def update_game_status(chat_id: int, status: str) -> None:
    """Update game status."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/update_game_status.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, status)


async def add_player_to_game(chat_id: int, player_id: UUID) -> None:
    """Add a player to game (if not already in)."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/add_player_to_game.sql")
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(sql, chat_id, player_id)


async def remove_player_from_game(chat_id: int, player_id: UUID) -> None:
    """Remove a player from game."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/remove_player_from_game.sql")
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(sql, chat_id, player_id)


async def delete_game(chat_id: int) -> None:
    """Delete game by chat ID."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/delete_game.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id)


async def get_game_info(chat_id: int) -> dict | None:
    """Get game info with pack name."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_info.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return dict(row) if row else None


async def get_players_with_stats(player_ids: list[UUID]) -> list[dict]:
    """Get players with their usernames and ELO ratings."""
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_players_with_stats.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


async def cleanup_stale_games() -> list[int]:
    """Delete games with 'registered' status older than 5 minutes. Returns list of deleted chat_ids."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/cleanup_stale_games.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [row['chat_id'] for row in rows]


async def bulk_update_player_scores(chat_id: int, score_changes: dict[UUID, int]) -> None:
    """Bulk update player scores in a single query.
    
    Args:
        chat_id: The chat ID of the game
        score_changes: Dict mapping player_id -> points to add (can be negative)
    """
    if not score_changes:
        return
    
    pool = Database.get_pool()
    get_scores_sql = Database.load_sql("games/get_game_scores.sql")
    update_sql = Database.load_sql("games/bulk_update_player_scores.sql")
    
    async with pool.acquire() as conn:
        # Get current scores
        row = await conn.fetchrow(get_scores_sql, chat_id)
        if not row:
            return
        
        current_scores = _parse_jsonb(row['scores'])
        
        # Apply all changes
        for player_id, points in score_changes.items():
            player_key = str(player_id)
            current = int(current_scores.get(player_key, 0))
            current_scores[player_key] = current + points
        
        # Update with the new scores in a single write
        await conn.execute(update_sql, chat_id, json.dumps(current_scores))


async def get_game_scores(chat_id: int) -> dict:
    """Get scores for a game. Returns dict of player_id -> score."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/get_game_scores.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, chat_id)
        return _parse_jsonb(row['scores']) if row else {}


async def assign_pack_to_game(chat_id: int, pack_short_name: str, pack_themes: list[int]) -> None:
    """Assign a pack and themes to a game."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/assign_pack_to_game.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, pack_short_name, pack_themes)


async def get_current_position(chat_id: int) -> dict:
    """Get current game position. Returns dict with 'theme' and 'question' keys."""
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
    """Set current game position (theme index and question cost)."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_current_position.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, int(theme), int(question))


async def set_number_of_themes(chat_id: int, number_of_themes: int) -> None:
    """Set number of themes for a game."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_number_of_themes.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, number_of_themes)


async def set_pack(chat_id: int, pack_short_name: str) -> None:
    """Set pack for a game."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_pack.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, chat_id, pack_short_name)


async def set_game_chat_id(old_chat_id: int, new_chat_id: int) -> None:
    """Transfer game to a new chat (game chat)."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/set_game_chat_id.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, old_chat_id, new_chat_id)


async def delete_all_games() -> None:
    """Delete all games."""
    pool = Database.get_pool()
    sql = Database.load_sql("games/delete_all_games.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql)

