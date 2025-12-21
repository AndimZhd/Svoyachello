-- Get game info with pack name and players with their ELO ratings
SELECT 
    g.id,
    g.chat_id,
    g.pack_short_name,
    g.number_of_themes,
    g.players,
    g.status,
    g.pack_short_name AS pack_name
FROM game g
WHERE g.chat_id = $1;

