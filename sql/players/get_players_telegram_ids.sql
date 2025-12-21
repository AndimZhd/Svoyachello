-- Get telegram_ids for a list of player UUIDs
SELECT id, telegram_id, username
FROM player
WHERE id = ANY($1);


