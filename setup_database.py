#!/usr/bin/env python3
"""
Database setup script for PostgreSQL chatbot database.
Run this script to create the database and user.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database():
    """Create PostgreSQL database and user for the chatbot"""

    # Database connection parameters
    db_host = "localhost"
    db_port = "5432"
    db_name = "chatbot_db"
    db_user = "chatbot_user"
    db_password = "password"

    # Admin connection (you'll need to provide admin credentials)
    admin_user = input("Enter PostgreSQL admin username (default: postgres): ").strip() or "postgres"
    admin_password = input("Enter PostgreSQL admin password: ").strip()

    try:
        # Connect to PostgreSQL as admin
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=admin_user,
            password=admin_password,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Create user if it doesn't exist
        print(f"Creating user '{db_user}'...")
        try:
            cursor.execute(f"CREATE USER {db_user} WITH PASSWORD '{db_password}';")
            print("✓ User created successfully")
        except psycopg2.Error as e:
            if "already exists" in str(e):
                print("✓ User already exists")
            else:
                raise

        # Create database if it doesn't exist
        print(f"Creating database '{db_name}'...")
        try:
            cursor.execute(f"CREATE DATABASE {db_name} OWNER {db_user};")
            print("✓ Database created successfully")
        except psycopg2.Error as e:
            if "already exists" in str(e):
                print("✓ Database already exists")
            else:
                raise

        # Grant privileges
        print("Granting privileges...")
        cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};")
        print("✓ Privileges granted")

        cursor.close()
        conn.close()

        print("\n🎉 Database setup completed successfully!")
        print(f"Database: {db_name}")
        print(f"User: {db_user}")
        print(f"Connection string: postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

    except psycopg2.Error as e:
        print(f"❌ Database setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("PostgreSQL Database Setup for Chatbot")
    print("=" * 40)
    create_database()