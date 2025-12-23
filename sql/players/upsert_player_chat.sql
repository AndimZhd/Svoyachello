-- Track that a player is in a specific chat
INSERT INTO player_chat (player_id, chat_id)
VALUES ($1, $2)
ON CONFLICT (player_id, chat_id) DO NOTHING;

