-- Insert or update player pack history
-- $1: player_id (UUID)
-- $2: pack_id (UUID)
-- $3: themes_played (VARCHAR) - comma-separated theme indices to add
INSERT INTO player_pack_history (player_id, pack_id, themes_played)
VALUES ($1, $2, $3)
ON CONFLICT (player_id, pack_id) DO UPDATE SET
    themes_played = CASE 
        WHEN player_pack_history.themes_played = '' THEN EXCLUDED.themes_played
        ELSE player_pack_history.themes_played || ',' || EXCLUDED.themes_played
    END;

