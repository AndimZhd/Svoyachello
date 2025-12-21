-- Get player statistics by Telegram ID (joins players and statistics tables)
SELECT p.username, s.*
FROM player p
JOIN statistics s ON s.user_id = p.id
WHERE p.telegram_id = $1;

