-- Set current game position (theme index and question index)
UPDATE game
SET current_position = jsonb_build_object('theme', $2::integer, 'question', $3::integer)
WHERE chat_id = $1;

