#!/usr/bin/env python3
"""
Quick database connection test
"""

import asyncio
import asyncpg
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(".env", override=True)

async def quick_test():
    database_url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {database_url[:50]}...")
    
    try:
        print("Attempting connection with 5 second timeout...")
        conn = await asyncio.wait_for(
            asyncpg.connect(database_url, statement_cache_size=0),
            timeout=5.0
        )
        print("✅ Connected successfully!")
        
        print("Testing simple query...")
        result = await asyncio.wait_for(
            conn.fetchval("SELECT 1"),
            timeout=3.0
        )
        print(f"✅ Query result: {result}")
        
        await conn.close()
        print("✅ Connection closed successfully!")
        
    except asyncio.TimeoutError:
        print("❌ Connection timed out - check your network or database URL")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(quick_test())