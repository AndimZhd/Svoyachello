-- Get players by multiple Telegram IDs
SELECT * FROM player WHERE telegram_id = ANY($1);

