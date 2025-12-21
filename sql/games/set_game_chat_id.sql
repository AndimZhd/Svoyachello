-- Set game chat_id (transfer game to game chat)
UPDATE game
SET chat_id = $2
WHERE chat_id = $1;

