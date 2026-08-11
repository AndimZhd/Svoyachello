-- Unban a pack for a player
UPDATE player_pack_history
SET is_banned = FALSE
WHERE player_id = (SELECT id FROM player WHERE telegram_id = $1)
  AND pack_id = $2
RETURNING *;
