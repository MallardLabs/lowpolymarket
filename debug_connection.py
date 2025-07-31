#!/usr/bin/env python3
"""
Debug database connection issues
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv(".env", override=True)

async def debug_connection():
    database_url = os.getenv("DATABASE_URL")
    print(f"Database URL: {database_url[:50]}...")
    
    try:
        print("Step 1: Attempting basic connection...")
        conn = await asyncio.wait_for(
            asyncpg.connect(database_url, statement_cache_size=0),
            timeout=5.0
        )
        print("✅ Connected!")
        
        print("Step 2: Testing simple SELECT 1...")
        result = await asyncio.wait_for(
            conn.fetchval("SELECT 1"),
            timeout=3.0
        )
        print(f"✅ SELECT 1 result: {result}")
        
        print("Step 3: Testing version query...")
        try:
            version = await asyncio.wait_for(
                conn.fetchval("SELECT version()"),
                timeout=3.0
            )
            print(f"✅ Version: {version[:100]}...")
        except asyncio.TimeoutError:
            print("❌ Version query timed out")
        except Exception as e:
            print(f"❌ Version query failed: {e}")
        
        print("Step 4: Testing current_database()...")
        try:
            db_name = await asyncio.wait_for(
                conn.fetchval("SELECT current_database()"),
                timeout=3.0
            )
            print(f"✅ Database name: {db_name}")
        except asyncio.TimeoutError:
            print("❌ Database name query timed out")
        except Exception as e:
            print(f"❌ Database name query failed: {e}")
        
        print("Step 5: Closing connection...")
        await conn.close()
        print("✅ Connection closed!")
        
    except asyncio.TimeoutError:
        print("❌ Initial connection timed out")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(debug_connection())