-- Get player rights by player_id
SELECT pr.*, p.telegram_id
FROM player_rights pr
JOIN player p ON pr.player_id = p.id
WHERE p.telegram_id = $1;

