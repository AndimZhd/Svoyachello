-- Assign a game to a game chat
UPDATE game_chat
SET game_id = $2
WHERE id = $1;


