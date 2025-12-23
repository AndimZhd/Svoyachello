from uuid import UUID

from database.connection import Database


async def create_statistics(player_id: UUID) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/create_statistics.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(sql, player_id)


async def get_player_statistics(telegram_id: int) -> dict | None:
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/get_user_statistics.sql")
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, telegram_id)
        return dict(row) if row else None


async def get_statistics_by_player_id(player_id: UUID) -> dict | None:
    pool = Database.get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM statistics WHERE user_id = $1",
            player_id
        )
        return dict(row) if row else None


async def get_rating() -> list[dict]:
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/get_rating.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [dict(row) for row in rows]


async def get_rating_by_players(player_ids: list[UUID]) -> list[dict]:
    if not player_ids:
        return []
    
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/get_rating_by_players.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, player_ids)
        return [dict(row) for row in rows]


async def get_rating_by_chat(chat_id: int) -> list[dict]:
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/get_rating_by_chat.sql")
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, chat_id)
        return [dict(row) for row in rows]


async def update_player_game_stats(
    player_id: UUID,
    game_score: int,
    is_winner: bool,
    correct_answers: int,
    wrong_answers: int,
    elo_change: int
) -> None:
    pool = Database.get_pool()
    sql = Database.load_sql("statistics/update_player_game_stats.sql")
    
    async with pool.acquire() as conn:
        await conn.execute(
            sql,
            player_id,
            game_score,
            is_winner,
            correct_answers,
            wrong_answers,
            elo_change
        )


def calculate_elo_changes(
    player_ratings: dict[UUID, int],
    player_scores: dict[UUID, int],
    k_factor: int = 32
) -> dict[UUID, int]:
    if len(player_ratings) < 2:
        return {pid: 0 for pid in player_ratings}
    
    players = list(player_ratings.keys())
    elo_changes: dict[UUID, int] = {pid: 0 for pid in players}
    
    for i, player_a in enumerate(players):
        for player_b in players[i + 1:]:
            rating_a = player_ratings[player_a]
            rating_b = player_ratings[player_b]
            score_a = player_scores.get(player_a, 0)
            score_b = player_scores.get(player_b, 0)
            
            expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
            expected_b = 1 - expected_a
            
            if score_a > score_b:
                actual_a, actual_b = 1.0, 0.0
            elif score_a < score_b:
                actual_a, actual_b = 0.0, 1.0
            else:
                actual_a, actual_b = 0.5, 0.5
            
            num_opponents = len(players) - 1
            change_a = int(k_factor * (actual_a - expected_a) / num_opponents)
            change_b = int(k_factor * (actual_b - expected_b) / num_opponents)
            
            elo_changes[player_a] += change_a
            elo_changes[player_b] += change_b
    
    return elo_changes
