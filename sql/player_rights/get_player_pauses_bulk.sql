-- Get number_of_pauses for multiple players by their telegram_ids
SELECT p.telegram_id, COALESCE(pr.number_of_pauses, 5) as number_of_pauses
FROM player p
LEFT JOIN player_rights pr ON pr.player_id = p.id
WHERE p.telegram_id = ANY($1);
