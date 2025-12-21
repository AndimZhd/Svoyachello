-- Create a new question pack
INSERT INTO pack (short_name, name, pack_file, number_of_themes)
VALUES ($1, $2, $3, $4)
RETURNING id;

