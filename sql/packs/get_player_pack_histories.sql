-- Get pack histories for multiple players
SELECT pph.player_id, pph.pack_id, pph.themes_played, p.short_name, p.name, p.pack_file
FROM player_pack_history pph
JOIN pack p ON p.id = pph.pack_id
WHERE pph.player_id = ANY($1);


