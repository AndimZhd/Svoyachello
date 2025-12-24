-- Add a spectator to the game
UPDATE game
SET spectators = array_append(spectators, $2)
WHERE chat_id = $1
  AND NOT ($2 = ANY(spectators));

