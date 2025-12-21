-- Get scores for a game
SELECT scores
FROM game
WHERE chat_id = $1;


