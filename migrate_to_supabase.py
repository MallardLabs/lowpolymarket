#!/usr/bin/env python3
"""
Migration script to move from in-memory prediction storage to Supabase
This script preserves all existing market data during the transition
"""

import os
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
import pickle

from database.supabase_client import SupabaseManager, PredictionDatabase
from dotenv import load_dotenv

load_dotenv()

class MigrationManager:
    def __init__(self):
        self.supabase_manager = SupabaseManager(
            url=os.getenv("DATABASE_SUPABASE_URL"),
            publishable_key=os.getenv("DATABASE_SUPABASE_PUBLISHABLE_KEY"),
            secret_key=os.getenv("DATABASE_SUPABASE_SECRET_KEY"),
            db_url=os.getenv("DATABASE_URL")
        )
        self.db = PredictionDatabase(self.supabase_manager)
        
    async def initialize(self):
        """Initialize database connection"""
        await self.supabase_manager.initialize()
        
    async def cleanup(self):
        """Cleanup database connections"""
        await self.supabase_manager.cleanup()
    
    async def backup_current_data(self, bot_instance=None) -> Dict[str, Any]:
        """
        Backup current in-memory prediction data
        This should be called while the bot is running to capture live data
        """
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'predictions': [],
            'guilds': {}
        }
        
        if bot_instance:
            # Get economy cog
            economy_cog = bot_instance.get_cog('Economy')
            if economy_cog and hasattr(economy_cog, 'predictions'):
                for prediction in economy_cog.predictions:
                    pred_data = {
                        'question': prediction.question,
                        'end_time': prediction.end_time.isoformat(),
                        'options': prediction.options,
                        'creator_id': prediction.creator_id,
                        'category': prediction.category,
                        'resolved': prediction.resolved,
                        'result': prediction.result,
                        'refunded': prediction.refunded,
                        'total_bets': prediction.total_bets,
                        'initial_liquidity': prediction.initial_liquidity,
                        'k_constant': prediction.k_constant,
                        'liquidity_pool': prediction.liquidity_pool,
                        'bets': {},
                        'votes': {}
                    }
                    
                    # Convert bets data
                    for option, user_bets in prediction.bets.items():
                        pred_data['bets'][option] = {}
                        for user_id, bet_info in user_bets.items():
                            pred_data['bets'][option][str(user_id)] = {
                                'amount': bet_info['amount'],
                                'shares': bet_info['shares']
                            }
                    
                    # Convert votes data
                    for option, voters in prediction.votes.items():
                        pred_data['votes'][option] = list(voters)
                    
                    backup_data['predictions'].append(pred_data)
                
                # Get guild information from bot
                for guild in bot_instance.guilds:
                    backup_data['guilds'][str(guild.id)] = {
                        'name': guild.name,
                        'member_count': guild.member_count
                    }
        
        # Save backup to file
        backup_filename = f"prediction_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f"Backup saved to {backup_filename}")
        return backup_data
    
    async def load_backup_data(self, backup_file: str) -> Dict[str, Any]:
        """Load backup data from file"""
        with open(backup_file, 'r') as f:
            return json.load(f)
    
    async def migrate_guilds(self, backup_data: Dict[str, Any]):
        """Migrate guild data to Supabase"""
        print("Migrating guilds...")
        
        for guild_id_str, guild_info in backup_data['guilds'].items():
            guild_id = int(guild_id_str)
            await self.supabase_manager.ensure_guild_exists(guild_id, guild_info['name'])
            print(f"Migrated guild: {guild_info['name']} ({guild_id})")
    
    async def migrate_predictions(self, backup_data: Dict[str, Any], default_guild_id: int):
        """Migrate prediction data to Supabase"""
        print("Migrating predictions...")
        
        for i, pred_data in enumerate(backup_data['predictions']):
            try:
                # Create prediction in database
                end_time = datetime.fromisoformat(pred_data['end_time'].replace('Z', '+00:00'))
                
                prediction_id = await self.db.create_prediction(
                    guild_id=default_guild_id,  # You may need to adjust this
                    question=pred_data['question'],
                    options=pred_data['options'],
                    creator_id=pred_data['creator_id'],
                    end_time=end_time,
                    category=pred_data.get('category'),
                    initial_liquidity=pred_data.get('initial_liquidity', 30000)
                )
                
                print(f"Created prediction {i+1}/{len(backup_data['predictions'])}: {pred_data['question'][:50]}...")
                
                # Update prediction status if resolved/refunded
                if pred_data['resolved'] or pred_data['refunded']:
                    status = 'refunded' if pred_data['refunded'] else 'resolved'
                    async with self.supabase_manager.pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE predictions 
                            SET status = $2, resolved = $3, result = $4, refunded = $5, total_bets = $6
                            WHERE id = $1
                        """, prediction_id, status, pred_data['resolved'], 
                            pred_data.get('result'), pred_data['refunded'], pred_data['total_bets'])
                
                # Migrate liquidity pools
                for option, liquidity in pred_data.get('liquidity_pool', {}).items():
                    await self.db.update_liquidity_pool(prediction_id, option, int(liquidity))
                
                # Migrate bets
                for option, user_bets in pred_data.get('bets', {}).items():
                    for user_id_str, bet_info in user_bets.items():
                        user_id = int(user_id_str)
                        amount = bet_info['amount']
                        shares = bet_info['shares']
                        price_per_share = amount / shares if shares > 0 else 0
                        
                        await self.db.place_bet(
                            prediction_id, user_id, default_guild_id, option,
                            amount, shares, price_per_share
                        )
                
                # Migrate votes
                for option, voters in pred_data.get('votes', {}).items():
                    for user_id in voters:
                        await self.db.add_resolution_vote(
                            prediction_id, user_id, default_guild_id, option
                        )
                
                print(f"Migrated all data for prediction: {pred_data['question'][:50]}...")
                
            except Exception as e:
                print(f"Error migrating prediction {i+1}: {e}")
                continue
    
    async def verify_migration(self, backup_data: Dict[str, Any], guild_id: int):
        """Verify that migration was successful"""
        print("Verifying migration...")
        
        # Get all predictions from database
        db_predictions = await self.db.get_predictions_by_status(guild_id)
        
        print(f"Original predictions: {len(backup_data['predictions'])}")
        print(f"Migrated predictions: {len(db_predictions)}")
        
        # Verify each prediction
        for orig_pred in backup_data['predictions']:
            # Find matching prediction in database
            db_pred = None
            for dp in db_predictions:
                if dp['question'] == orig_pred['question']:
                    db_pred = dp
                    break
            
            if db_pred:
                print(f"✓ Found: {orig_pred['question'][:50]}...")
                
                # Verify bets count
                orig_bet_count = sum(len(user_bets) for user_bets in orig_pred.get('bets', {}).values())
                
                # Count bets in database
                async with self.supabase_manager.pool.acquire() as conn:
                    db_bet_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM bets WHERE prediction_id = $1
                    """, db_pred['id'])
                
                if orig_bet_count == db_bet_count:
                    print(f"  ✓ Bets match: {orig_bet_count}")
                else:
                    print(f"  ⚠ Bet count mismatch: {orig_bet_count} vs {db_bet_count}")
            else:
                print(f"✗ Missing: {orig_pred['question'][:50]}...")
        
        print("Migration verification complete!")

async def main():
    """Main migration function"""
    print("Starting Supabase migration...")
    
    migration = MigrationManager()
    await migration.initialize()
    
    try:
        # Option 1: Load from existing backup file
        backup_file = input("Enter backup file path (or press Enter to skip): ").strip()
        
        if backup_file and os.path.exists(backup_file):
            backup_data = await migration.load_backup_data(backup_file)
            print(f"Loaded backup from {backup_file}")
        else:
            print("No backup file provided. You'll need to create a backup first.")
            print("Run this script with your bot instance to create a backup:")
            print("  backup_data = await migration.backup_current_data(bot)")
            return
        
        # Get default guild ID for migration
        guild_id_input = input("Enter the main Discord server ID for migration: ").strip()
        if not guild_id_input:
            print("Guild ID is required for migration")
            return
        
        default_guild_id = int(guild_id_input)
        
        # Perform migration
        await migration.migrate_guilds(backup_data)
        await migration.migrate_predictions(backup_data, default_guild_id)
        
        # Verify migration
        await migration.verify_migration(backup_data, default_guild_id)
        
        print("\n" + "="*50)
        print("Migration completed successfully!")
        print("Next steps:")
        print("1. Update your bot to use DatabaseEconomy cog")
        print("2. Test the bot functionality")
        print("3. Monitor for any issues")
        print("="*50)
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        await migration.cleanup()

if __name__ == "__main__":
    asyncio.run(main())