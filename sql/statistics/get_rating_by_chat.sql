-- Get ratings for all players who are tracked in a specific chat
SELECT
    p.id,
    p.first_name,
    p.last_name,
    p.username,
    s.elo_rating,
    s.games_played,
    s.games_won
FROM
    player p
JOIN
    statistics s ON p.id = s.user_id
JOIN
    player_chat pc ON p.id = pc.player_id
WHERE
    pc.chat_id = $1
ORDER BY
    s.elo_rating DESC;

