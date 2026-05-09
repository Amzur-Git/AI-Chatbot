#!/usr/bin/env python3
"""
Database migration - simply recreates all tables with updated schema.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from sqlalchemy import inspect, text
from backend.app.database import engine
from backend.app.models import Base

async def main():
    print("Updating database schema...")
    
    async with engine.begin() as conn:
        # Drop existing tables with CASCADE and recreate with new schema
        print("Dropping existing tables...")
        await conn.execute(text("DROP TABLE IF EXISTS attachments CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS user_credentials CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS chat_session_messages CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS chat_messages CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        print("[OK] Tables dropped")
        
        print("Creating new tables with updated schema...")
        await conn.run_sync(Base.metadata.create_all)
        print("[OK] Tables created with thread_id support")
    
    print("\n[SUCCESS] Database migration completed successfully!")
    print("All tables have been recreated with the new schema.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
