-- Create a new game for a chat
INSERT INTO game (chat_id)
VALUES ($1)
ON CONFLICT (chat_id) DO NOTHING
RETURNING id;

