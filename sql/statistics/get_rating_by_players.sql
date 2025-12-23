-- Get players with their ELO ratings for specific player IDs, sorted by ELO descending
SELECT 
    p.first_name,
    p.last_name,
    p.username,
    s.elo_rating,
    s.games_played,
    s.games_won
FROM statistics s
JOIN player p ON s.user_id = p.id
WHERE p.id = ANY($1)
ORDER BY s.elo_rating DESC;

