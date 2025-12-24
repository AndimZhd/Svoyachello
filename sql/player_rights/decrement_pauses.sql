-- Decrement number_of_pauses by 1 for a player
UPDATE player_rights
SET number_of_pauses = number_of_pauses - 1
WHERE player_id = (SELECT id FROM player WHERE telegram_id = $1)
  AND number_of_pauses > 0
RETURNING *;

