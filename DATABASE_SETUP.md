# Chatbot Database Setup Guide

This guide will help you set up PostgreSQL database for the chatbot application.

## Prerequisites

1. **PostgreSQL Installation**: Make sure PostgreSQL is installed and running on your system.
   - Download from: https://www.postgresql.org/download/
   - Or use a package manager: `brew install postgresql` (macOS) / `apt install postgresql` (Ubuntu)

2. **Python Dependencies**: Install the required Python packages:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

## Database Setup

### Option 1: Automatic Setup (Recommended)

Run the setup script:
```bash
python setup_database.py
```

This script will:
- Create a database user `chatbot_user`
- Create a database `chatbot_db`
- Grant necessary permissions

### Option 2: Manual Setup

If you prefer manual setup, run these commands in PostgreSQL:

```sql
-- Connect as postgres admin user
CREATE USER chatbot_user WITH PASSWORD 'password';
CREATE DATABASE chatbot_db OWNER chatbot_user;
GRANT ALL PRIVILEGES ON DATABASE chatbot_db TO chatbot_user;
```

## Environment Configuration

Update your `backend/.env` file with the correct database URL:

```
DATABASE_URL=postgresql://chatbot_user:password@localhost/chatbot_db
```

## Starting the Application

1. **Start PostgreSQL service** (if not already running):
   - Windows: `pg_ctl start -D "C:\Program Files\PostgreSQL\15\data"`
   - macOS: `brew services start postgresql`
   - Linux: `sudo systemctl start postgresql`

2. **Run the application**:
   ```bash
   .\run-dev.ps1
   ```

## Troubleshooting

### Connection Issues
- Make sure PostgreSQL is running
- Check that the database URL in `.env` is correct
- Verify the user has permissions on the database

### Authentication Issues
- Ensure Google OAuth credentials are properly configured
- Check that the redirect URI matches your application URL
- Verify that only @amzur.com emails can access

### Migration Issues
- If you get table creation errors, you may need to drop and recreate the database
- The application will automatically create tables on startup

## Database Schema

The application creates these tables:
- `users`: Stores user information (email, name, Google ID)
- `chat_messages`: Stores chat conversations linked to users

## Security Notes

- Change the `SECRET_KEY` in `.env` for production
- Use strong passwords for database users
- Configure PostgreSQL to only accept local connections in production
- Set up SSL/TLS for database connections