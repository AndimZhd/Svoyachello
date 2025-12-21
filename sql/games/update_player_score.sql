-- Update a player's score (add points to current score)
UPDATE game
SET scores = jsonb_set(
    scores,
    ARRAY[$2::text],
    to_jsonb(COALESCE((scores->>$2::text)::integer, 0) + $3)
)
WHERE chat_id = $1;


