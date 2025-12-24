-- Database schema for Своя игра bot
-- Run this script to set up the database

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Player table (basic info only)
CREATE TABLE IF NOT EXISTS player (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Statistics table (all game stats)
CREATE TABLE IF NOT EXISTS statistics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    
    -- ELO Rating
    elo_rating INTEGER DEFAULT 1000 NOT NULL,
    
    -- Game statistics
    games_played INTEGER DEFAULT 0 NOT NULL,
    games_won INTEGER DEFAULT 0 NOT NULL,
    win_percentage REAL DEFAULT 0 NOT NULL,
    
    -- Answer statistics
    correct_answers INTEGER DEFAULT 0 NOT NULL,
    wrong_answers INTEGER DEFAULT 0 NOT NULL,
    
    -- Points statistics
    total_points_earned INTEGER DEFAULT 0 NOT NULL,
    highest_game_score INTEGER DEFAULT 0 NOT NULL,
    average_game_score INTEGER DEFAULT 0 NOT NULL,
    
    -- Streaks
    current_win_streak INTEGER DEFAULT 0 NOT NULL,
    best_win_streak INTEGER DEFAULT 0 NOT NULL,
    
    -- Timestamps
    last_played_at TIMESTAMP
);

-- Pack table (question packs)
CREATE TABLE IF NOT EXISTS pack (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    short_name VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    pack_file JSONB NOT NULL,
    number_of_themes INTEGER NOT NULL
);

-- Game table (active games)
CREATE TABLE IF NOT EXISTS game (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id BIGINT UNIQUE NOT NULL,
    origin_chat_id BIGINT,
    pack_short_name VARCHAR(50) REFERENCES pack(short_name) ON DELETE SET NULL,
    number_of_themes INTEGER DEFAULT 6 NOT NULL,
    pack_themes INTEGER[] DEFAULT '{}',
    players UUID[] DEFAULT '{}',
    scores JSONB DEFAULT '{}' NOT NULL,
    current_position JSONB DEFAULT '{"theme": 0, "question": 0}' NOT NULL,
    status VARCHAR(50) DEFAULT 'registered' NOT NULL,
    game_mode VARCHAR(20) DEFAULT 'public' NOT NULL,
    invite_link VARCHAR(255),
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Game chat table (chats used for games)
CREATE TABLE IF NOT EXISTS game_chat (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id BIGINT NOT NULL,
    game_id UUID REFERENCES game(id) ON DELETE CASCADE
);

-- Player pack history (tracks which themes each player has played from each pack)
CREATE TABLE IF NOT EXISTS player_pack_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    pack_id UUID NOT NULL REFERENCES pack(id) ON DELETE CASCADE,
    themes_played VARCHAR(255) DEFAULT '' NOT NULL,
    UNIQUE(player_id, pack_id)
);

-- Player chat tracking (tracks which players are in which chats)
CREATE TABLE IF NOT EXISTS player_chat (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    UNIQUE(player_id, chat_id)
);


-- Player rights table (controls permissions for game commands)
CREATE TABLE IF NOT EXISTS player_rights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID UNIQUE NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    can_abort BOOLEAN DEFAULT TRUE NOT NULL,
    number_of_pauses INTEGER DEFAULT 5 NOT NULL,
    can_abort_all BOOLEAN DEFAULT FALSE NOT NULL,
    can_correct BOOLEAN DEFAULT TRUE NOT NULL
);

-- Function to automatically update updated_at on any row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on game table
CREATE TRIGGER trigger_game_updated_at
    BEFORE UPDATE ON game
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_player_telegram_id ON player(telegram_id);
CREATE INDEX IF NOT EXISTS idx_statistics_elo_rating ON statistics(elo_rating DESC);
CREATE INDEX IF NOT EXISTS idx_statistics_user_id ON statistics(user_id);
CREATE INDEX IF NOT EXISTS idx_pack_short_name ON pack(short_name);
CREATE INDEX IF NOT EXISTS idx_game_chat_id ON game(chat_id);
CREATE INDEX IF NOT EXISTS idx_game_status ON game(status);
CREATE INDEX IF NOT EXISTS idx_game_chat_chat_id ON game_chat(chat_id);
CREATE INDEX IF NOT EXISTS idx_game_chat_game_id ON game_chat(game_id);
CREATE INDEX IF NOT EXISTS idx_player_pack_history_player_id ON player_pack_history(player_id);
CREATE INDEX IF NOT EXISTS idx_player_pack_history_pack_id ON player_pack_history(pack_id);
CREATE INDEX IF NOT EXISTS idx_player_chat_player_id ON player_chat(player_id);
CREATE INDEX IF NOT EXISTS idx_player_chat_chat_id ON player_chat(chat_id);
CREATE INDEX IF NOT EXISTS idx_player_rights_player_id ON player_rights(player_id);
