-- Ensure player has rights record with defaults, return existing or new
WITH inserted AS (
    INSERT INTO player_rights (player_id)
    SELECT id FROM player WHERE telegram_id = $1
    ON CONFLICT (player_id) DO NOTHING
    RETURNING *
)
SELECT pr.*, p.telegram_id
FROM player_rights pr
JOIN player p ON pr.player_id = p.id
WHERE p.telegram_id = $1;
