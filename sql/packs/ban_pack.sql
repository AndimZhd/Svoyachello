-- Ban a pack for a player (or create history entry if doesn't exist)
INSERT INTO player_pack_history (player_id, pack_id, themes_played, is_banned)
VALUES (
    (SELECT id FROM player WHERE telegram_id = $1),
    $2,
    '',
    TRUE
)
ON CONFLICT (player_id, pack_id)
DO UPDATE SET is_banned = TRUE
RETURNING *;
