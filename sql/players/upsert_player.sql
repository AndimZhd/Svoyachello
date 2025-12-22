-- Insert a new player or update username/first_name/last_name if already exists
-- Returns the full player record
INSERT INTO player (telegram_id, username, first_name, last_name)
VALUES ($1, $2, $3, $4)
ON CONFLICT (telegram_id) DO UPDATE SET
    username = EXCLUDED.username,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name
RETURNING *;


