-- Get all banned packs for a player by telegram_id
SELECT p.short_name, p.name, p.id as pack_id
FROM player_pack_history pph
JOIN pack p ON p.id = pph.pack_id
WHERE pph.player_id = (SELECT id FROM player WHERE telegram_id = $1)
  AND pph.is_banned = TRUE
ORDER BY p.short_name;
