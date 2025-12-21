-- Update game status
UPDATE game
SET status = $2
WHERE chat_id = $1;

