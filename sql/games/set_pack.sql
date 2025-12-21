-- Set pack for a game
UPDATE game
SET pack_short_name = $2
WHERE chat_id = $1;

