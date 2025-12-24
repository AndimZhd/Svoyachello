-- Add spectators column to game table
ALTER TABLE game ADD COLUMN IF NOT EXISTS spectators UUID[] DEFAULT '{}';

