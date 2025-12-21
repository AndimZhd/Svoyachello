-- Get current game position
SELECT current_position FROM game WHERE chat_id = $1;

