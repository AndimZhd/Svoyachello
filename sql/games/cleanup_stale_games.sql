-- Delete games with 'registered' status older than 5 minutes
DELETE FROM game
WHERE status = 'registered'
  AND updated_at < NOW() - INTERVAL '5 minutes'
RETURNING chat_id;


