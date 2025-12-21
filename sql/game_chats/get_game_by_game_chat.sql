-- Get game info by game_chat's chat_id
SELECT g.*
FROM game g
JOIN game_chat gc ON gc.game_id = g.id
WHERE gc.chat_id = $1;


