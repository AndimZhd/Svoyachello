-- Get an available game chat (one with no game_id)
SELECT id, chat_id
FROM game_chat
WHERE game_id IS NULL
LIMIT 1;


