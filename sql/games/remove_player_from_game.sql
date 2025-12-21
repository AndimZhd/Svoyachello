-- Remove a player from game
UPDATE game
SET players = array_remove(players, $2)
WHERE chat_id = $1;


