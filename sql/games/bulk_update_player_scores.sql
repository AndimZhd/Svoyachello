-- Bulk update player scores in a game
-- $1: chat_id
-- $2: new_scores (JSONB) - complete scores object to replace
UPDATE game
SET scores = $2
WHERE chat_id = $1;

