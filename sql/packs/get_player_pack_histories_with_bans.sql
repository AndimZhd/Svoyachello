-- Get player pack histories including ban status
SELECT pph.*, p.telegram_id
FROM player_pack_history pph
JOIN player p ON p.id = pph.player_id
WHERE pph.player_id = ANY($1);
