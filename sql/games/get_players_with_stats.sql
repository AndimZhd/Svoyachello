-- Get players with their usernames and ELO ratings for a game
SELECT 
    p.id,
    p.username,
    s.elo_rating
FROM player p
JOIN statistics s ON s.user_id = p.id
WHERE p.id = ANY($1);

