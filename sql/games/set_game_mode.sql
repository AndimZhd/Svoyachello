-- Set game mode (public/private) for a game
UPDATE game
SET game_mode = $2
WHERE chat_id = $1;

