-- Add a player to game (if not already in)
UPDATE game
SET players = array_append(players, $2)
WHERE chat_id = $1
  AND NOT ($2 = ANY(players));

