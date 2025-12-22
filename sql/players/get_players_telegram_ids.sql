-- Get telegram_ids for a list of player UUIDs
SELECT id, telegram_id, username, first_name, last_name
FROM player
WHERE id = ANY($1);


