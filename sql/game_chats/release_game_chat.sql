-- Release a game chat (set game_id to NULL)
UPDATE game_chat
SET game_id = NULL
WHERE game_id = $1;


