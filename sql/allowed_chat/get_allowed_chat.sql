SELECT id, chat_id, is_allowed
FROM allowed_chat
WHERE chat_id = $1;

