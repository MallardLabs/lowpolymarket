#!/usr/bin/env python3
"""
Simplified database setup script
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env", override=True)

async def setup_database():
    database_url = os.getenv("DATABASE_URL")
    
    print("🔧 Setting up database schema...")
    print(f"Connecting to: {database_url[:50]}...")
    
    try:
        # Connect with timeout
        conn = await asyncio.wait_for(
            asyncpg.connect(database_url, statement_cache_size=0),
            timeout=10.0
        )
        print("✅ Connected to database!")
        
        # Read minimal schema
        schema_file = project_root / "supabase_schema_minimal.sql"
        if not schema_file.exists():
            print("❌ Schema file not found!")
            return False
        
        schema_sql = schema_file.read_text()
        print(f"📝 Read schema file ({len(schema_sql)} characters)")
        
        # Execute schema in one go (simpler approach)
        print("🚀 Executing schema...")
        await asyncio.wait_for(
            conn.execute(schema_sql),
            timeout=60.0
        )
        print("✅ Schema executed successfully!")
        
        # Test that tables were created
        print("🧪 Testing table creation...")
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        table_names = [row['table_name'] for row in tables]
        print(f"✅ Created tables: {', '.join(table_names)}")
        
        await conn.close()
        print("✅ Database setup completed successfully!")
        print("✅ Connection closed!")
        return True
        
    except asyncio.TimeoutError:
        print("❌ Database operation timed out")
        return False
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_database())
    if success:
        print("\n🎉 Database is ready for your Discord bot!")
    else:
        print("\n❌ Database setup failed. Check the errors above.")
        exit(1)