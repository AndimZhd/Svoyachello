-- Set a player's score to a specific value
UPDATE game
SET scores = jsonb_set(scores, ARRAY[$2::text], to_jsonb($3))
WHERE chat_id = $1;


