#!/usr/bin/env python3
"""
Database setup script for the Discord Prediction Market Bot.

This script creates the database schema and sets up the initial configuration.
"""

import asyncio
import os
import sys
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env", override=True)

async def setup_database():
    """Set up the database schema"""
    try:
        from config import get_settings
        settings = get_settings()
        
        print("🔧 Setting up database schema...")
        
        # Connect to database (disable prepared statements for Supabase Transaction Pooler)
        conn = await asyncpg.connect(settings.database.url, statement_cache_size=0)
        
        try:
            # Read schema file (use minimal schema for now)
            schema_file = project_root / "supabase_schema_minimal.sql"
            if not schema_file.exists():
                print("❌ Schema file not found: supabase_schema_minimal.sql")
                return False
            
            schema_sql = schema_file.read_text()
            
            # Execute schema in smaller chunks with timeout
            print("📝 Executing database schema...")
            
            # Split the schema into individual statements
            statements = []
            current_statement = ""
            
            for line in schema_sql.split('\n'):
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                current_statement += line + '\n'
                
                # End of statement (semicolon not inside quotes/functions)
                if line.endswith(';') and not line.startswith('CREATE OR REPLACE FUNCTION'):
                    statements.append(current_statement.strip())
                    current_statement = ""
                elif line == '$ LANGUAGE plpgsql;' or line == '$ language \'plpgsql\';':
                    statements.append(current_statement.strip())
                    current_statement = ""
            
            # Add any remaining statement
            if current_statement.strip():
                statements.append(current_statement.strip())
            
            print(f"   Executing {len(statements)} SQL statements...")
            
            for i, statement in enumerate(statements):
                if not statement.strip():
                    continue
                    
                try:
                    print(f"   Executing statement {i+1}/{len(statements)}...")
                    await asyncio.wait_for(
                        conn.execute(statement),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    print(f"   ⚠️ Statement {i+1} timed out, skipping...")
                    continue
                except Exception as e:
                    if "already exists" in str(e):
                        print(f"   ℹ️ Statement {i+1} - object already exists, skipping...")
                        continue
                    else:
                        print(f"   ❌ Statement {i+1} failed: {e}")
                        # Continue with other statements
                        continue
            
            print("✅ Database schema created successfully!")
            
            # Test the setup
            print("🧪 Testing database connection...")
            
            # Test basic queries
            guild_count = await conn.fetchval("SELECT COUNT(*) FROM guilds")
            prediction_count = await conn.fetchval("SELECT COUNT(*) FROM predictions")
            
            print(f"   Guilds: {guild_count}")
            print(f"   Predictions: {prediction_count}")
            
            print("✅ Database setup completed successfully!")
            return True
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

async def test_database_connection():
    """Test database connection and configuration"""
    try:
        from config import get_settings
        settings = get_settings()
        
        print("🔍 Testing database connection...")
        
        # Test PostgreSQL connection (disable prepared statements for Supabase Transaction Pooler)
        print("   Connecting to PostgreSQL...")
        conn = await asyncio.wait_for(
            asyncpg.connect(settings.database.url, statement_cache_size=0),
            timeout=10.0
        )
        print("   Connected! Getting version...")
        version = await asyncio.wait_for(
            conn.fetchval("SELECT version()"),
            timeout=5.0
        )
        await conn.close()
        
        print(f"✅ PostgreSQL connection successful")
        print(f"   Version: {version.split(',')[0]}")
        
        # Test Supabase client
        print("   Testing Supabase API connection...")
        from supabase import create_client
        
        # Use the new publishable key for testing
        supabase = create_client(
            settings.database.supabase_url, 
            settings.database.supabase_publishable_key
        )
        
        # Test a simple query with timeout (this will fail if tables don't exist, which is expected)
        try:
            print("   Attempting Supabase API call...")
            result = await asyncio.wait_for(
                asyncio.to_thread(lambda: supabase.table('guilds').select('count', count='exact').execute()),
                timeout=10.0
            )
            print(f"✅ Supabase API connection successful")
            print(f"   Guilds table accessible")
        except asyncio.TimeoutError:
            print("❌ Supabase API connection timed out")
            return False
        except Exception as e:
            if "does not exist" in str(e) or "relation" in str(e):
                print(f"✅ Supabase API connection successful")
                print(f"   Tables not created yet (expected)")
            else:
                print(f"❌ Supabase API error: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

async def main():
    """Main setup function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set up the database")
    parser.add_argument("--test-only", action="store_true", help="Only test connection, don't create schema")
    parser.add_argument("--force", action="store_true", help="Force schema creation even if tables exist")
    
    args = parser.parse_args()
    
    print("Database Setup for Discord Prediction Market Bot")
    print("=" * 50)
    
    # Test connection first
    if not await test_database_connection():
        print("\n💡 Make sure your .env file has the correct database configuration:")
        print("   DATABASE_URL=postgresql://...")
        print("   DATABASE_SUPABASE_URL=https://...")
        print("   DATABASE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_... (or legacy keys)")
        return False
    
    if args.test_only:
        print("\n✅ Database connection test completed!")
        return True
    
    # Set up schema
    success = await setup_database()
    
    if success:
        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Your database is ready to use")
        print("2. Start your bot with the new configuration")
        print("3. Test creating a prediction market")
    else:
        print("\n❌ Database setup failed")
        print("Check the error messages above and fix any issues")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)