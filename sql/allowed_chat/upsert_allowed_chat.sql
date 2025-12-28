INSERT INTO allowed_chat (chat_id, is_allowed)
VALUES ($1, $2)
ON CONFLICT (chat_id) 
DO UPDATE SET is_allowed = EXCLUDED.is_allowed;

