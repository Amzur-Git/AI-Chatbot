#!/usr/bin/env python3
"""Test database connection and verify thread_id column exists"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from sqlalchemy import inspect, text
from backend.app.database import engine

async def main():
    print("Testing database connection and schema...")
    
    async with engine.connect() as conn:
        # Check if thread_id column exists
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='chat_messages' AND column_name='thread_id'
        """))
        
        if result.fetchone():
            print("[OK] thread_id column exists in chat_messages table")
        else:
            print("[ERROR] thread_id column NOT found in chat_messages table")
            print("Available columns:")
            col_result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='chat_messages' ORDER BY ordinal_position
            """))
            for (col,) in col_result:
                print(f"  - {col}")
            return False
    
    print("[SUCCESS] Database schema is correct!")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
