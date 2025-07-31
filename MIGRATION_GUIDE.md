# Database Schema Migration Guide

This guide helps you migrate from the basic schema to the enhanced schema incrementally.

## Migration Strategy

You can migrate in phases without downtime:

### Phase 1: Core Enhancements (Optional)
```sql
-- Add user tracking
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    username TEXT,
    total_bets INTEGER DEFAULT 0,
    total_winnings BIGINT DEFAULT 0,
    accuracy_rate DECIMAL(5,2) DEFAULT 0.00,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add categories
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    emoji TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(guild_id, name)
);

-- Add category reference to predictions
ALTER TABLE predictions ADD COLUMN category_id UUID REFERENCES categories(id) ON DELETE SET NULL;
```

### Phase 2: Enhanced Features (Optional)
```sql
-- Add market types
CREATE TYPE market_type AS ENUM ('binary', 'multiple_choice', 'scalar');
ALTER TABLE predictions ADD COLUMN market_type market_type DEFAULT 'binary';

-- Add description and metadata
ALTER TABLE predictions ADD COLUMN description TEXT;
ALTER TABLE predictions ADD COLUMN tags TEXT[];
ALTER TABLE predictions ADD COLUMN image_url TEXT;

-- Add price tracking to liquidity pools
ALTER TABLE liquidity_pools ADD COLUMN current_price DECIMAL(10,6) DEFAULT 0.5;
ALTER TABLE liquidity_pools ADD COLUMN price_history JSONB DEFAULT '[]'::jsonb;
```

### Phase 3: Advanced Features (Optional)
```sql
-- Add notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ
);

-- Add activity logging
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
    user_id BIGINT,
    action TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Zero-Downtime Migration

1. **Add new tables** (doesn't affect existing functionality)
2. **Add new columns** with defaults (backward compatible)
3. **Update application code** to use new features gradually
4. **Migrate data** in background processes

## Rollback Strategy

All migrations are designed to be backward compatible:
- New tables don't affect existing queries
- New columns have sensible defaults
- Existing code continues to work unchanged