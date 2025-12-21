-- Create statistics record for a player (if not exists)
INSERT INTO statistics (user_id)
VALUES ($1)
ON CONFLICT (user_id) DO NOTHING;

