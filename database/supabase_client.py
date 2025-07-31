import os
import asyncio
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import asyncpg
from supabase import create_client, Client
import json
from decimal import Decimal

class SupabaseManager:
    def __init__(self, url: str, publishable_key: str, secret_key: str, db_url: str):
        # Use publishable key for general operations
        self.supabase: Client = create_client(url, publishable_key)
        self.publishable_key = publishable_key
        self.secret_key = secret_key
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self):
        """Initialize the database connection pool"""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
    async def cleanup(self):
        """Cleanup database connections"""
        if self.pool:
            await self.pool.close()
            
    async def ensure_guild_exists(self, guild_id: int, guild_name: str):
        """Ensure guild exists in database"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guilds (id, name) 
                VALUES ($1, $2) 
                ON CONFLICT (id) DO UPDATE SET 
                    name = EXCLUDED.name,
                    updated_at = NOW()
            """, guild_id, guild_name)

class PredictionDatabase:
    def __init__(self, supabase_manager: SupabaseManager):
        self.db = supabase_manager
        
    async def create_prediction(
        self, 
        guild_id: int,
        question: str,
        options: List[str],
        creator_id: int,
        end_time: datetime,
        category: Optional[str] = None,
        initial_liquidity: int = 30000
    ) -> str:
        """Create a new prediction market"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Insert prediction
                prediction_id = await conn.fetchval("""
                    INSERT INTO predictions (
                        guild_id, question, options, creator_id, 
                        end_time, category, initial_liquidity, k_constant
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, guild_id, question, options, creator_id, 
                    end_time, category, initial_liquidity, initial_liquidity ** 2)
                
                return str(prediction_id)
    
    async def get_active_predictions(self, guild_id: int) -> List[Dict]:
        """Get all active predictions for a guild"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT p.*, 
                       json_agg(
                           json_build_object(
                               'option', lp.option_name,
                               'liquidity', lp.current_liquidity
                           )
                       ) as liquidity_data
                FROM predictions p
                LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
                WHERE p.guild_id = $1 AND p.status = 'active' AND p.end_time > NOW()
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """, guild_id)
            
            return [dict(row) for row in rows]
    
    async def get_prediction_by_id(self, prediction_id: str) -> Optional[Dict]:
        """Get prediction by ID with all related data"""
        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT p.*,
                       json_agg(
                           json_build_object(
                               'option', lp.option_name,
                               'liquidity', lp.current_liquidity
                           )
                       ) as liquidity_data
                FROM predictions p
                LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
                WHERE p.id = $1
                GROUP BY p.id
            """, prediction_id)
            
            return dict(row) if row else None
    
    async def place_bet(
        self,
        prediction_id: str,
        user_id: int,
        guild_id: int,
        option_name: str,
        amount_bet: int,
        shares_owned: float,
        price_per_share: float
    ) -> bool:
        """Place a bet and update liquidity pools atomically"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Insert bet
                    await conn.execute("""
                        INSERT INTO bets (
                            prediction_id, user_id, guild_id, option_name,
                            amount_bet, shares_owned, price_per_share
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, prediction_id, user_id, guild_id, option_name,
                        amount_bet, shares_owned, price_per_share)
                    
                    return True
                except Exception as e:
                    print(f"Error placing bet: {e}")
                    return False
    
    async def update_liquidity_pool(
        self,
        prediction_id: str,
        option_name: str,
        new_liquidity: int
    ):
        """Update liquidity pool for an option"""
        async with self.db.pool.acquire() as conn:
            await conn.execute("""
                UPDATE liquidity_pools 
                SET current_liquidity = $3, updated_at = NOW()
                WHERE prediction_id = $1 AND option_name = $2
            """, prediction_id, option_name, new_liquidity)
    
    async def get_user_bets(
        self, 
        prediction_id: str, 
        user_id: int
    ) -> List[Dict]:
        """Get all bets by a user for a specific prediction"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM bets 
                WHERE prediction_id = $1 AND user_id = $2
                ORDER BY created_at DESC
            """, prediction_id, user_id)
            
            return [dict(row) for row in rows]
    
    async def get_option_bets(
        self, 
        prediction_id: str, 
        option_name: str
    ) -> List[Dict]:
        """Get all bets for a specific option"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, SUM(amount_bet) as total_amount, SUM(shares_owned) as total_shares
                FROM bets 
                WHERE prediction_id = $1 AND option_name = $2
                GROUP BY user_id
            """, prediction_id, option_name)
            
            return [dict(row) for row in rows]
    
    async def get_liquidity_pools(self, prediction_id: str) -> Dict[str, int]:
        """Get current liquidity for all options"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT option_name, current_liquidity
                FROM liquidity_pools
                WHERE prediction_id = $1
            """, prediction_id)
            
            return {row['option_name']: row['current_liquidity'] for row in rows}
    
    async def add_resolution_vote(
        self,
        prediction_id: str,
        user_id: int,
        guild_id: int,
        voted_option: str
    ) -> bool:
        """Add a resolution vote"""
        async with self.db.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO resolution_votes (prediction_id, user_id, guild_id, voted_option)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (prediction_id, user_id) DO UPDATE SET
                        voted_option = EXCLUDED.voted_option
                """, prediction_id, user_id, guild_id, voted_option)
                return True
            except Exception as e:
                print(f"Error adding vote: {e}")
                return False
    
    async def get_resolution_votes(self, prediction_id: str) -> Dict[str, int]:
        """Get vote counts for each option"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT voted_option, COUNT(*) as vote_count
                FROM resolution_votes
                WHERE prediction_id = $1
                GROUP BY voted_option
            """, prediction_id)
            
            return {row['voted_option']: row['vote_count'] for row in rows}
    
    async def has_user_voted(self, prediction_id: str, user_id: int) -> bool:
        """Check if user has already voted on resolution"""
        async with self.db.pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM resolution_votes
                WHERE prediction_id = $1 AND user_id = $2
            """, prediction_id, user_id)
            
            return count > 0
    
    async def resolve_prediction(
        self,
        prediction_id: str,
        winning_option: str,
        resolved_by: int,
        total_pool: int,
        total_winning_bets: int,
        vote_count: int
    ) -> bool:
        """Resolve a prediction market"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Update prediction status
                    await conn.execute("""
                        UPDATE predictions 
                        SET status = 'resolved', resolved = true, result = $2, updated_at = NOW()
                        WHERE id = $1
                    """, prediction_id, winning_option)
                    
                    # Record resolution
                    await conn.execute("""
                        INSERT INTO market_resolutions (
                            prediction_id, winning_option, resolved_by,
                            total_pool, total_winning_bets, vote_count
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """, prediction_id, winning_option, resolved_by,
                        total_pool, total_winning_bets, vote_count)
                    
                    return True
                except Exception as e:
                    print(f"Error resolving prediction: {e}")
                    return False
    
    async def record_payout(
        self,
        prediction_id: str,
        user_id: int,
        guild_id: int,
        bet_amount: int,
        shares_owned: float,
        payout_amount: int
    ):
        """Record a payout for transparency"""
        async with self.db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO payouts (
                    prediction_id, user_id, guild_id,
                    bet_amount, shares_owned, payout_amount
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """, prediction_id, user_id, guild_id,
                bet_amount, shares_owned, payout_amount)
    
    async def refund_prediction(self, prediction_id: str) -> List[Dict]:
        """Mark prediction as refunded and return all bets for refunding"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Update prediction status
                await conn.execute("""
                    UPDATE predictions 
                    SET status = 'refunded', refunded = true, resolved = true, updated_at = NOW()
                    WHERE id = $1
                """, prediction_id)
                
                # Get all bets for refunding
                rows = await conn.fetch("""
                    SELECT user_id, SUM(amount_bet) as total_amount
                    FROM bets
                    WHERE prediction_id = $1
                    GROUP BY user_id
                """, prediction_id)
                
                return [dict(row) for row in rows]
    
    async def get_predictions_by_status(
        self, 
        guild_id: int, 
        status: str = None
    ) -> List[Dict]:
        """Get predictions filtered by status"""
        async with self.db.pool.acquire() as conn:
            if status:
                rows = await conn.fetch("""
                    SELECT * FROM prediction_summary
                    WHERE guild_id = $1 AND status = $2
                    ORDER BY end_time DESC
                """, guild_id, status)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM prediction_summary
                    WHERE guild_id = $1
                    ORDER BY end_time DESC
                """, guild_id)
            
            return [dict(row) for row in rows]
    
    async def get_expired_predictions(self) -> List[Dict]:
        """Get predictions that have ended but not resolved"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, guild_id, question, creator_id, end_time
                FROM predictions
                WHERE status = 'active' AND end_time <= NOW()
            """, )
            
            return [dict(row) for row in rows]
    
    async def get_predictions_for_auto_refund(self, hours_threshold: int = 120) -> List[Dict]:
        """Get predictions that should be auto-refunded"""
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, guild_id, question, creator_id
                FROM predictions
                WHERE status = 'ended' 
                AND end_time <= NOW() - INTERVAL '%s hours'
                AND NOT resolved
            """, hours_threshold)
            
            return [dict(row) for row in rows]