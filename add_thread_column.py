#!/usr/bin/env python3
"""
Add thread_id column to chat_messages table
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from sqlalchemy import text
from backend.app.database import engine

async def main():
    print("Adding thread_id column to chat_messages...")
    
    async with engine.begin() as conn:
        try:
            # Add thread_id column
            await conn.execute(text("""
                ALTER TABLE chat_messages
                ADD COLUMN thread_id INTEGER
            """))
            print("[OK] thread_id column added")
            
            # Create index
            await conn.execute(text("""
                CREATE INDEX idx_chat_messages_thread_id ON chat_messages(thread_id)
            """))
            print("[OK] Index created on thread_id")
            
        except Exception as e:
            if "already exists" in str(e):
                print("[OK] thread_id column already exists")
            else:
                print(f"Error: {e}")
                raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("\n[SUCCESS] Database updated successfully!")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)
