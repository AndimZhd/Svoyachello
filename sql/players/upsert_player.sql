-- Insert a new player or update username if already exists
-- Returns the player's UUID
INSERT INTO player (telegram_id, username)
VALUES ($1, $2)
ON CONFLICT (telegram_id) DO UPDATE SET
    username = EXCLUDED.username
RETURNING id;


