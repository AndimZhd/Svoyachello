SELECT id, chat_id, is_allowed
FROM allowed_chat
WHERE is_allowed = TRUE
ORDER BY chat_id;

