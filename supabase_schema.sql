-- Supabase Schema for Discord Prediction Market Bot
-- Multi-tenant architecture with guild_id separation

-- Enable Row Level Security
ALTER DATABASE postgres SET "app.jwt_secret" TO 'your-jwt-secret-here';

-- Create custom types
CREATE TYPE prediction_status AS ENUM ('active', 'ended', 'resolved', 'refunded');
CREATE TYPE resolution_status AS ENUM ('pending', 'resolved', 'refunded');

-- Guilds table for Discord server management
CREATE TABLE guilds (
    id BIGINT PRIMARY KEY, -- Discord guild ID
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- Predictions table - core market data
CREATE TABLE predictions (
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
    k_constant BIGINT DEFAULT 900000000, -- initial_liquidity^2
    total_bets INTEGER DEFAULT 0,
    
    -- Constraints
    CONSTRAINT valid_result CHECK (result IS NULL OR result = ANY(options)),
    CONSTRAINT valid_end_time CHECK (end_time > created_at)
);

-- Liquidity pools for AMM pricing
CREATE TABLE liquidity_pools (
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
CREATE TABLE bets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    option_name TEXT NOT NULL,
    amount_bet INTEGER NOT NULL CHECK (amount_bet > 0),
    shares_owned DECIMAL(20,8) NOT NULL CHECK (shares_owned > 0),
    price_per_share DECIMAL(20,8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes for performance
    INDEX idx_bets_prediction_user (prediction_id, user_id),
    INDEX idx_bets_guild_user (guild_id, user_id),
    INDEX idx_bets_option (prediction_id, option_name)
);

-- Resolution votes for admin consensus
CREATE TABLE resolution_votes (
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
CREATE TABLE market_resolutions (
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
CREATE TABLE payouts (
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
CREATE INDEX idx_predictions_guild_status ON predictions(guild_id, status);
CREATE INDEX idx_predictions_end_time ON predictions(end_time) WHERE status = 'active';
CREATE INDEX idx_predictions_creator ON predictions(creator_id, guild_id);
CREATE INDEX idx_liquidity_pools_prediction ON liquidity_pools(prediction_id);
CREATE INDEX idx_bets_user_guild ON bets(user_id, guild_id);
CREATE INDEX idx_resolution_votes_prediction ON resolution_votes(prediction_id);

-- Row Level Security Policies
ALTER TABLE guilds ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE liquidity_pools ENABLE ROW LEVEL SECURITY;
ALTER TABLE bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE resolution_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;

-- RLS Policies (adjust based on your authentication method)
CREATE POLICY "Guild access" ON guilds FOR ALL USING (true); -- Adjust based on your auth
CREATE POLICY "Prediction guild isolation" ON predictions FOR ALL USING (true); -- Will be refined
CREATE POLICY "Liquidity pool access" ON liquidity_pools FOR ALL USING (true);
CREATE POLICY "Bet guild isolation" ON bets FOR ALL USING (true);
CREATE POLICY "Vote guild isolation" ON resolution_votes FOR ALL USING (true);
CREATE POLICY "Resolution access" ON market_resolutions FOR ALL USING (true);
CREATE POLICY "Payout access" ON payouts FOR ALL USING (true);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_guilds_updated_at BEFORE UPDATE ON guilds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_predictions_updated_at BEFORE UPDATE ON predictions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_liquidity_pools_updated_at BEFORE UPDATE ON liquidity_pools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to initialize liquidity pools when prediction is created
CREATE OR REPLACE FUNCTION initialize_liquidity_pools()
RETURNS TRIGGER AS $$
DECLARE
    option_name TEXT;
BEGIN
    -- Create liquidity pool for each option
    FOREACH option_name IN ARRAY NEW.options
    LOOP
        INSERT INTO liquidity_pools (prediction_id, option_name, current_liquidity)
        VALUES (NEW.id, option_name, NEW.initial_liquidity);
    END LOOP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_liquidity_pools_trigger
    AFTER INSERT ON predictions
    FOR EACH ROW
    EXECUTE FUNCTION initialize_liquidity_pools();

-- Function to update total_bets when bets are placed
CREATE OR REPLACE FUNCTION update_prediction_totals()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE predictions 
        SET total_bets = total_bets + NEW.amount_bet,
            updated_at = NOW()
        WHERE id = NEW.prediction_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE predictions 
        SET total_bets = total_bets - OLD.amount_bet,
            updated_at = NOW()
        WHERE id = OLD.prediction_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_prediction_totals_trigger
    AFTER INSERT OR DELETE ON bets
    FOR EACH ROW
    EXECUTE FUNCTION update_prediction_totals();

-- Real-time subscriptions setup
-- Enable realtime for tables that need live updates
ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE bets;
ALTER PUBLICATION supabase_realtime ADD TABLE liquidity_pools;
ALTER PUBLICATION supabase_realtime ADD TABLE resolution_votes;

-- Views for common queries
CREATE VIEW active_predictions AS
SELECT 
    p.*,
    COUNT(DISTINCT b.user_id) as unique_bettors,
    COALESCE(SUM(b.amount_bet), 0) as total_volume
FROM predictions p
LEFT JOIN bets b ON p.id = b.prediction_id
WHERE p.status = 'active' AND p.end_time > NOW()
GROUP BY p.id;

CREATE VIEW prediction_summary AS
SELECT 
    p.id,
    p.guild_id,
    p.question,
    p.options,
    p.category,
    p.end_time,
    p.status,
    p.total_bets,
    COUNT(DISTINCT b.user_id) as unique_bettors,
    json_agg(
        json_build_object(
            'option', lp.option_name,
            'liquidity', lp.current_liquidity,
            'total_bets', COALESCE(option_bets.total, 0),
            'bet_count', COALESCE(option_bets.count, 0)
        )
    ) as option_data
FROM predictions p
LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
LEFT JOIN bets b ON p.id = b.prediction_id
LEFT JOIN (
    SELECT 
        prediction_id,
        option_name,
        SUM(amount_bet) as total,
        COUNT(*) as count
    FROM bets
    GROUP BY prediction_id, option_name
) option_bets ON lp.prediction_id = option_bets.prediction_id 
    AND lp.option_name = option_bets.option_name
GROUP BY p.id;