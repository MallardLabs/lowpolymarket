-- Minimal Supabase Schema for Discord Prediction Market Bot
-- This is a simplified version to test basic functionality

-- Create custom types
CREATE TYPE prediction_status AS ENUM ('active', 'ended', 'resolved', 'refunded');

-- Guilds table for Discord server management
CREATE TABLE IF NOT EXISTS guilds (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- Predictions table - core market data
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    options TEXT[] NOT NULL CHECK (array_length(options, 1) >= 2),
    creator_id BIGINT NOT NULL,
    category TEXT,
    end_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Market state
    status prediction_status DEFAULT 'active',
    resolved BOOLEAN DEFAULT FALSE,
    result TEXT,
    refunded BOOLEAN DEFAULT FALSE,
    
    -- AMM parameters
    initial_liquidity INTEGER DEFAULT 30000,
    k_constant BIGINT DEFAULT 900000000,
    total_bets INTEGER DEFAULT 0,
    
    -- Constraints
    CONSTRAINT valid_result CHECK (result IS NULL OR result = ANY(options)),
    CONSTRAINT valid_end_time CHECK (end_time > created_at)
);

-- Liquidity pools for AMM pricing
CREATE TABLE IF NOT EXISTS liquidity_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    option_name TEXT NOT NULL,
    current_liquidity INTEGER NOT NULL DEFAULT 30000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure one pool per option per prediction
    UNIQUE(prediction_id, option_name)
);

-- User bets with AMM share tracking
CREATE TABLE IF NOT EXISTS bets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    option_name TEXT NOT NULL,
    amount_bet INTEGER NOT NULL CHECK (amount_bet > 0),
    shares_owned DECIMAL(20,8) NOT NULL CHECK (shares_owned > 0),
    price_per_share DECIMAL(20,8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Resolution votes for admin consensus
CREATE TABLE IF NOT EXISTS resolution_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    voted_option TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- One vote per user per prediction
    UNIQUE(prediction_id, user_id)
);

-- Market resolutions tracking
CREATE TABLE IF NOT EXISTS market_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    winning_option TEXT NOT NULL,
    resolved_by BIGINT NOT NULL,
    resolved_at TIMESTAMPTZ DEFAULT NOW(),
    total_pool INTEGER NOT NULL,
    total_winning_bets INTEGER NOT NULL,
    vote_count INTEGER NOT NULL DEFAULT 0
);

-- Payout tracking for transparency
CREATE TABLE IF NOT EXISTS payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    bet_amount INTEGER NOT NULL,
    shares_owned DECIMAL(20,8) NOT NULL,
    payout_amount INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_predictions_guild_status ON predictions(guild_id, status);
CREATE INDEX IF NOT EXISTS idx_predictions_end_time ON predictions(end_time) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_predictions_creator ON predictions(creator_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_liquidity_pools_prediction ON liquidity_pools(prediction_id);
CREATE INDEX IF NOT EXISTS idx_bets_user_guild ON bets(user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_bets_prediction_user ON bets(prediction_id, user_id);
CREATE INDEX IF NOT EXISTS idx_bets_guild_user ON bets(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_bets_option ON bets(prediction_id, option_name);
CREATE INDEX IF NOT EXISTS idx_resolution_votes_prediction ON resolution_votes(prediction_id);