-- Add allowed_chat table to control which chats can register for games
CREATE TABLE IF NOT EXISTS allowed_chat (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id BIGINT UNIQUE NOT NULL,
    is_allowed BOOLEAN DEFAULT TRUE NOT NULL
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_allowed_chat_chat_id ON allowed_chat(chat_id);
CREATE INDEX IF NOT EXISTS idx_allowed_chat_is_allowed ON allowed_chat(is_allowed);

