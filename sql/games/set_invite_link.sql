-- Set invite link for a game
UPDATE game
SET invite_link = $2
WHERE chat_id = $1;

