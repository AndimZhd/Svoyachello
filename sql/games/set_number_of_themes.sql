-- Set number of themes for a game
UPDATE game
SET number_of_themes = $2
WHERE chat_id = $1;

