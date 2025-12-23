-- Set game chat_id (transfer game to game chat)
-- Also stores the original chat_id as origin_chat_id
UPDATE game
SET chat_id = $2,
    origin_chat_id = $1
WHERE chat_id = $1;

