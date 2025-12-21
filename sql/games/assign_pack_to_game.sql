-- Assign a pack and themes to a game
UPDATE game
SET pack_short_name = $2,
    pack_themes = $3
WHERE chat_id = $1;


