-- Update pack file and number of themes
UPDATE pack
SET pack_file = $2, number_of_themes = $3
WHERE short_name = $1
RETURNING id;

