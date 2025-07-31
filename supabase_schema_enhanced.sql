-- Enhanced Supabase Schema for Discord Prediction Market Bot
-- Multi-tenant architecture with guild_id separation + Future-proofing

-- Enable Row Level Security
ALTER DATABASE postgres SET "app.jwt_secret" TO 'your-jwt-secret-here';

-- Create custom types
CREATE TYPE prediction_status AS ENUM ('active', 'ended', 'resolved', 'refunded', 'cancelled', 'paused');
CREATE TYPE resolution_status AS ENUM ('pending', 'resolved', 'refunded', 'disputed');
CREATE TYPE bet_status AS ENUM ('active', 'cancelled', 'settled');
CREATE TYPE market_type AS ENUM ('binary', 'multiple_choice', 'scalar', 'conditional');
CREATE TYPE guild_tier AS ENUM ('free', 'premium', 'enterprise');

-- Guilds table for Discord server management
CREATE TABLE guilds (
    id BIGINT PRIMARY KEY, -- Discord guild ID
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Guild configuration
    settings JSONB DEFAULT '{}'::jsonb,
    tier guild_tier DEFAULT 'free',
    
    -- Feature flags
    features JSONB DEFAULT '{
        "max_predictions": 10,
        "max_bet_amount": 1000000,
        "allow_categories": true,
        "allow_conditional_markets": false,
        "allow_scalar_markets": false,
        "custom_resolution_time": false
    }'::jsonb,
    
    -- Statistics
    total_predictions INTEGER DEFAULT 0,
    total_volume BIGINT DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    
    -- Moderation
    is_active BOOLEAN DEFAULT true,
    suspended_until TIMESTAMPTZ,
    suspension_reason TEXT
);

-- Users table for cross-guild user data
CREATE TABLE users (
    id BIGINT PRIMARY KEY, -- Discord user ID
    username TEXT,
    discriminator TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- User statistics
    total_bets INTEGER DEFAULT 0,
    total_winnings BIGINT DEFAULT 0,
    total_losses BIGINT DEFAULT 0,
    accuracy_rate DECIMAL(5,2) DEFAULT 0.00,
    
    -- User preferences
    preferences JSONB DEFAULT '{
        "notifications": true,
        "auto_resolve_votes": false,
        "default_bet_amount": 100
    }'::jsonb,
    
    -- Moderation
    is_banned BOOLEAN DEFAULT false,
    banned_until TIMESTAMPTZ,
    ban_reason TEXT
);

-- Categories for organizing predictions
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    emoji TEXT,
    color TEXT, -- Hex color for UI
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Category settings
    settings JSONB DEFAULT '{
        "min_duration_hours": 1,
        "max_duration_hours": 720,
        "require_approval": false,
        "auto_resolve": false
    }'::jsonb,
    
    UNIQUE(guild_id, name)
);

-- Enhanced Predictions table - core market data
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    creator_id BIGINT NOT NULL,
    
    -- Market definition
    question TEXT NOT NULL,
    description TEXT, -- Detailed description
    options TEXT[] NOT NULL CHECK (array_length(options, 1) >= 2),
    market_type market_type DEFAULT 'binary',
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ NOT NULL,
    resolution_deadline TIMESTAMPTZ, -- When resolution must be completed
    
    -- Market state
    status prediction_status DEFAULT 'active',
    resolved BOOLEAN DEFAULT FALSE,
    result TEXT,
    result_value DECIMAL(20,8), -- For scalar markets
    refunded BOOLEAN DEFAULT FALSE,
    
    -- AMM parameters
    initial_liquidity INTEGER DEFAULT 30000,
    k_constant BIGINT DEFAULT 900000000, -- initial_liquidity^2
    total_bets INTEGER DEFAULT 0,
    total_volume BIGINT DEFAULT 0,
    
    -- Market metadata
    tags TEXT[], -- For filtering/searching
    source_url TEXT, -- Reference link
    image_url TEXT, -- Market image
    
    -- Resolution data
    resolved_at TIMESTAMPTZ,
    resolved_by BIGINT,
    resolution_source TEXT, -- How was it resolved
    
    -- Moderation
    is_featured BOOLEAN DEFAULT false,
    requires_approval BOOLEAN DEFAULT false,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT valid_result CHECK (result IS NULL OR result = ANY(options)),
    CONSTRAINT valid_end_time CHECK (end_time > created_at),
    CONSTRAINT valid_resolution_deadline CHECK (resolution_deadline IS NULL OR resolution_deadline > end_time)
);

-- Enhanced Liquidity pools for AMM pricing
CREATE TABLE liquidity_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    option_name TEXT NOT NULL,
    current_liquidity INTEGER NOT NULL DEFAULT 30000,
    initial_liquidity INTEGER NOT NULL DEFAULT 30000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Pool statistics
    total_volume INTEGER DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    
    -- Price tracking
    current_price DECIMAL(10,6) DEFAULT 0.5, -- Current implied probability
    price_history JSONB DEFAULT '[]'::jsonb, -- Historical prices
    
    -- Ensure one pool per option per prediction
    UNIQUE(prediction_id, option_name)
);

-- Enhanced User bets with AMM share tracking
CREATE TABLE bets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    
    -- Bet details
    option_name TEXT NOT NULL,
    amount_bet INTEGER NOT NULL CHECK (amount_bet > 0),
    shares_owned DECIMAL(20,8) NOT NULL CHECK (shares_owned > 0),
    price_per_share DECIMAL(20,8) NOT NULL,
    
    -- Bet metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status bet_status DEFAULT 'active',
    
    -- Settlement data
    settled_at TIMESTAMPTZ,
    payout_amount INTEGER DEFAULT 0,
    profit_loss INTEGER DEFAULT 0,
    
    -- Transaction tracking
    transaction_hash TEXT, -- For blockchain integration
    fee_paid INTEGER DEFAULT 0,
    
    -- Indexes for performance
    INDEX idx_bets_prediction_user (prediction_id, user_id),
    INDEX idx_bets_guild_user (guild_id, user_id),
    INDEX idx_bets_option (prediction_id, option_name),
    INDEX idx_bets_status (status),
    INDEX idx_bets_created_at (created_at)
);

-- Enhanced Resolution votes for admin consensus
CREATE TABLE resolution_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    
    -- Vote details
    voted_option TEXT NOT NULL,
    confidence INTEGER CHECK (confidence >= 1 AND confidence <= 10), -- Confidence level
    reasoning TEXT, -- Why they voted this way
    evidence_url TEXT, -- Supporting evidence
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Vote metadata
    weight INTEGER DEFAULT 1, -- Vote weight (for weighted voting)
    is_final BOOLEAN DEFAULT false, -- Final resolution vote
    
    -- One vote per user per prediction
    UNIQUE(prediction_id, user_id)
);

-- Market resolutions tracking (enhanced)
CREATE TABLE market_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    
    -- Resolution details
    winning_option TEXT NOT NULL,
    resolved_by BIGINT NOT NULL,
    resolved_at TIMESTAMPTZ DEFAULT NOW(),
    resolution_method TEXT, -- 'admin', 'consensus', 'oracle', 'automatic'
    
    -- Market statistics
    total_pool INTEGER NOT NULL,
    total_winning_bets INTEGER NOT NULL,
    total_losing_bets INTEGER NOT NULL,
    vote_count INTEGER NOT NULL DEFAULT 0,
    
    -- Payout information
    total_payouts INTEGER DEFAULT 0,
    house_edge INTEGER DEFAULT 0,
    
    -- Resolution metadata
    evidence JSONB DEFAULT '{}'::jsonb,
    dispute_period_end TIMESTAMPTZ,
    is_disputed BOOLEAN DEFAULT false
);

-- Enhanced Payout tracking for transparency
CREATE TABLE payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    bet_id UUID REFERENCES bets(id) ON DELETE SET NULL,
    
    -- Payout details
    bet_amount INTEGER NOT NULL,
    shares_owned DECIMAL(20,8) NOT NULL,
    payout_amount INTEGER NOT NULL,
    profit_loss INTEGER NOT NULL,
    
    -- Payout metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    transaction_hash TEXT, -- For blockchain integration
    
    -- Fee tracking
    platform_fee INTEGER DEFAULT 0,
    guild_fee INTEGER DEFAULT 0
);

-- Activity log for audit trail
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    user_id BIGINT,
    prediction_id UUID REFERENCES predictions(id) ON DELETE SET NULL,
    
    -- Activity details
    action TEXT NOT NULL, -- 'create_prediction', 'place_bet', 'resolve', etc.
    details JSONB DEFAULT '{}'::jsonb,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    
    -- Indexes
    INDEX idx_activity_guild_time (guild_id, created_at),
    INDEX idx_activity_user_time (user_id, created_at),
    INDEX idx_activity_action (action)
);

-- Notifications system
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    guild_id BIGINT REFERENCES guilds(id) ON DELETE CASCADE,
    
    -- Notification content
    type TEXT NOT NULL, -- 'bet_won', 'prediction_resolved', 'market_ending', etc.
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}'::jsonb,
    
    -- Notification state
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    
    -- Delivery channels
    discord_sent BOOLEAN DEFAULT false,
    email_sent BOOLEAN DEFAULT false,
    
    INDEX idx_notifications_user_unread (user_id, read_at) WHERE read_at IS NULL
);

-- Performance indexes
CREATE INDEX idx_predictions_guild_status ON predictions(guild_id, status);
CREATE INDEX idx_predictions_end_time ON predictions(end_time) WHERE status = 'active';
CREATE INDEX idx_predictions_creator ON predictions(creator_id, guild_id);
CREATE INDEX idx_predictions_category ON predictions(category_id) WHERE category_id IS NOT NULL;
CREATE INDEX idx_predictions_featured ON predictions(is_featured) WHERE is_featured = true;
CREATE INDEX idx_liquidity_pools_prediction ON liquidity_pools(prediction_id);
CREATE INDEX idx_bets_user_guild ON bets(user_id, guild_id);
CREATE INDEX idx_resolution_votes_prediction ON resolution_votes(prediction_id);
CREATE INDEX idx_users_stats ON users(total_bets, accuracy_rate);

-- Full-text search indexes
CREATE INDEX idx_predictions_search ON predictions USING gin(to_tsvector('english', question || ' ' || COALESCE(description, '')));
CREATE INDEX idx_categories_search ON categories USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));

-- Row Level Security Policies
ALTER TABLE guilds ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE liquidity_pools ENABLE ROW LEVEL SECURITY;
ALTER TABLE bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE resolution_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_resolutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- RLS Policies (basic - adjust based on your authentication method)
CREATE POLICY "Guild access" ON guilds FOR ALL USING (true);
CREATE POLICY "User access" ON users FOR ALL USING (true);
CREATE POLICY "Category guild isolation" ON categories FOR ALL USING (true);
CREATE POLICY "Prediction guild isolation" ON predictions FOR ALL USING (true);
CREATE POLICY "Liquidity pool access" ON liquidity_pools FOR ALL USING (true);
CREATE POLICY "Bet guild isolation" ON bets FOR ALL USING (true);
CREATE POLICY "Vote guild isolation" ON resolution_votes FOR ALL USING (true);
CREATE POLICY "Resolution access" ON market_resolutions FOR ALL USING (true);
CREATE POLICY "Payout access" ON payouts FOR ALL USING (true);
CREATE POLICY "Activity log access" ON activity_log FOR ALL USING (true);
CREATE POLICY "Notification user access" ON notifications FOR ALL USING (true);

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

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_predictions_updated_at BEFORE UPDATE ON predictions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_liquidity_pools_updated_at BEFORE UPDATE ON liquidity_pools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_resolution_votes_updated_at BEFORE UPDATE ON resolution_votes
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
        INSERT INTO liquidity_pools (prediction_id, option_name, current_liquidity, initial_liquidity)
        VALUES (NEW.id, option_name, NEW.initial_liquidity, NEW.initial_liquidity);
    END LOOP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_liquidity_pools_trigger
    AFTER INSERT ON predictions
    FOR EACH ROW
    EXECUTE FUNCTION initialize_liquidity_pools();

-- Function to update prediction totals when bets are placed
CREATE OR REPLACE FUNCTION update_prediction_totals()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE predictions 
        SET total_bets = total_bets + 1,
            total_volume = total_volume + NEW.amount_bet,
            updated_at = NOW()
        WHERE id = NEW.prediction_id;
        
        -- Update guild statistics
        UPDATE guilds 
        SET total_volume = total_volume + NEW.amount_bet
        WHERE id = NEW.guild_id;
        
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE predictions 
        SET total_bets = total_bets - 1,
            total_volume = total_volume - OLD.amount_bet,
            updated_at = NOW()
        WHERE id = OLD.prediction_id;
        
        -- Update guild statistics
        UPDATE guilds 
        SET total_volume = total_volume - OLD.amount_bet
        WHERE id = OLD.guild_id;
        
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_prediction_totals_trigger
    AFTER INSERT OR DELETE ON bets
    FOR EACH ROW
    EXECUTE FUNCTION update_prediction_totals();

-- Function to update user statistics
CREATE OR REPLACE FUNCTION update_user_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Update user bet count
        INSERT INTO users (id, total_bets) 
        VALUES (NEW.user_id, 1)
        ON CONFLICT (id) DO UPDATE SET 
            total_bets = users.total_bets + 1;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' AND OLD.status != NEW.status AND NEW.status = 'settled' THEN
        -- Update user winnings/losses when bet is settled
        IF NEW.profit_loss > 0 THEN
            UPDATE users SET total_winnings = total_winnings + NEW.profit_loss WHERE id = NEW.user_id;
        ELSE
            UPDATE users SET total_losses = total_losses + ABS(NEW.profit_loss) WHERE id = NEW.user_id;
        END IF;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_stats_trigger
    AFTER INSERT OR UPDATE ON bets
    FOR EACH ROW
    EXECUTE FUNCTION update_user_stats();

-- Real-time subscriptions setup
ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE bets;
ALTER PUBLICATION supabase_realtime ADD TABLE liquidity_pools;
ALTER PUBLICATION supabase_realtime ADD TABLE resolution_votes;
ALTER PUBLICATION supabase_realtime ADD TABLE notifications;

-- Enhanced Views for common queries
CREATE VIEW active_predictions AS
SELECT 
    p.*,
    c.name as category_name,
    c.emoji as category_emoji,
    COUNT(DISTINCT b.user_id) as unique_bettors,
    COALESCE(SUM(b.amount_bet), 0) as total_volume,
    AVG(lp.current_price) as avg_price
FROM predictions p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN bets b ON p.id = b.prediction_id AND b.status = 'active'
LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
WHERE p.status = 'active' AND p.end_time > NOW()
GROUP BY p.id, c.name, c.emoji;

CREATE VIEW prediction_summary AS
SELECT 
    p.id,
    p.guild_id,
    p.question,
    p.description,
    p.options,
    p.market_type,
    p.category_id,
    c.name as category_name,
    p.end_time,
    p.status,
    p.total_bets,
    p.total_volume,
    COUNT(DISTINCT b.user_id) as unique_bettors,
    json_agg(
        json_build_object(
            'option', lp.option_name,
            'liquidity', lp.current_liquidity,
            'price', lp.current_price,
            'total_bets', COALESCE(option_bets.total, 0),
            'bet_count', COALESCE(option_bets.count, 0)
        )
    ) as option_data
FROM predictions p
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
LEFT JOIN bets b ON p.id = b.prediction_id AND b.status = 'active'
LEFT JOIN (
    SELECT 
        prediction_id,
        option_name,
        SUM(amount_bet) as total,
        COUNT(*) as count
    FROM bets
    WHERE status = 'active'
    GROUP BY prediction_id, option_name
) option_bets ON lp.prediction_id = option_bets.prediction_id 
    AND lp.option_name = option_bets.option_name
GROUP BY p.id, c.name;

-- User leaderboard view
CREATE VIEW user_leaderboard AS
SELECT 
    u.id,
    u.username,
    u.total_bets,
    u.total_winnings,
    u.total_losses,
    (u.total_winnings - u.total_losses) as net_profit,
    u.accuracy_rate,
    RANK() OVER (ORDER BY (u.total_winnings - u.total_losses) DESC) as profit_rank,
    RANK() OVER (ORDER BY u.accuracy_rate DESC) as accuracy_rank
FROM users u
WHERE u.total_bets > 0
ORDER BY net_profit DESC;

-- Guild statistics view
CREATE VIEW guild_stats AS
SELECT 
    g.id,
    g.name,
    g.tier,
    g.total_predictions,
    g.total_volume,
    g.active_users,
    COUNT(DISTINCT p.id) as current_predictions,
    COUNT(DISTINCT CASE WHEN p.status = 'active' THEN p.id END) as active_predictions,
    AVG(p.total_volume) as avg_prediction_volume
FROM guilds g
LEFT JOIN predictions p ON g.id = p.guild_id
WHERE g.is_active = true
GROUP BY g.id, g.name, g.tier, g.total_predictions, g.total_volume, g.active_users;