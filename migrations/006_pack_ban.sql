-- Add is_banned column to player_pack_history table
-- This allows players to ban packs from random selection

ALTER TABLE player_pack_history
ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE NOT NULL;

-- Create index for efficient filtering of banned packs
CREATE INDEX IF NOT EXISTS idx_player_pack_history_is_banned ON player_pack_history(player_id, is_banned);
