# Amzur Gemini Chatbot with Database

A full-stack chatbot application featuring Google OAuth authentication, PostgreSQL database storage, and Gemini AI integration via LiteLLM proxy.

## Features

- 🔐 **Google OAuth Authentication** - Login with Amzur (@amzur.com) accounts only
- 💬 **AI Chat Interface** - Chat with Gemini AI through LiteLLM proxy
- 🗄️ **PostgreSQL Database** - Persistent chat history storage
- 🎨 **Modern UI** - React + TypeScript frontend with Tailwind CSS
- 🚀 **FastAPI Backend** - Async Python API with SQLAlchemy ORM

## Prerequisites

- **PostgreSQL** - Database server (see DATABASE_SETUP.md)
- **Python 3.11+** - Backend runtime
- **Node.js 18+** - Frontend build tools
- **VS Code** - Recommended editor

## Quick Start

### 1. Database Setup

First, set up PostgreSQL database:

```bash
# Option 1: Automatic setup
python setup_database.py

# Option 2: Manual setup (see DATABASE_SETUP.md)
```

### 2. Environment Configuration

```bash
# Copy environment template
copy .env.example .env

# Edit .env with your values:
# - LITELLM_API_KEY: Your Amzur LiteLLM virtual key
# - DATABASE_URL: PostgreSQL connection string
# - GOOGLE_CLIENT_ID/SECRET: Google OAuth credentials
```

### 3. Install Dependencies & Run

```powershell
# Install all dependencies and start servers
.\run-dev.ps1
```

The application will be available at:
- **Frontend**: http://localhost:5174
- **Backend API**: http://localhost:8000

## Project Structure

```
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI app & routes
│   │   ├── config.py       # Settings & configuration
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── database.py     # Database connection
│   │   ├── auth.py         # JWT authentication
│   │   └── routes/         # API route handlers
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API services
│   │   └── types/          # TypeScript types
│   └── package.json       # Node dependencies
├── setup_database.py      # Database setup script
└── run-dev.ps1           # Development launcher
```

## API Endpoints

### Authentication
- `GET /api/auth/google/login` - Get Google OAuth URL
- `GET /api/auth/google/callback` - Handle OAuth callback
- `GET /api/auth/me` - Get current user info

### Chat
- `POST /api/chat` - Send message to AI (requires auth)
- `GET /api/history` - Get user's chat history (requires auth)

## Database Schema

- **users**: User accounts (email, name, Google ID)
- **chat_messages**: Chat conversations (user_id, role, content, timestamp)

## Development

### Backend Development

```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```powershell
cd frontend
npm run dev
```

### Database Migrations

Tables are created automatically on startup. For schema changes, update `models.py` and restart the application.

## Security

- JWT token-based authentication
- Google OAuth 2.0 integration
- Domain-restricted access (@amzur.com only)
- CORS protection
- SQL injection prevention via SQLAlchemy

## Troubleshooting

See `DATABASE_SETUP.md` for database-related issues.

### Common Issues

1. **Database connection failed**
   - Ensure PostgreSQL is running
   - Check DATABASE_URL in .env
   - Run `python setup_database.py`

2. **Google OAuth not working**
   - Verify Google credentials in .env
   - Check redirect URI matches your domain
   - Ensure @amzur.com domain restriction

3. **Chat not responding**
   - Check LiteLLM API key
   - Verify backend is running on port 8000
   - Check browser console for errors

```powershell
cd backend
.\start.ps1
```

```powershell
cd frontend
.\start.ps1
```

From the repo root:

```powershell
.\start-all.ps1
```

Or use the single-window launcher:

```powershell
.\run-dev.ps1
```

## Frontend Setup
Install the frontend dependencies:

```powershell
cd frontend
npm install
```

### Run the frontend

```powershell
cd frontend
npm run dev
```

The frontend is configured to proxy `/api` calls to `http://localhost:8000`.

## Run the LiteLLM test script
```powershell
cd backend
.\.venv\Scripts\activate
python ..\test_litellm_setup.py
```

## Notes from the service setup checklist
- `LITELLM_API_KEY` is the Amzur virtual key, not an OpenAI key.
- `GEMINI_API_KEY` is the API key used by the chatbot backend.
- `LITELLM_PROXY_URL` should be `https://litellm.amzur.com`.
- Supabase connection strings must use `postgresql+asyncpg://`.
- Google OAuth redirect URI must match exactly the value in your Cloud Console.
- Add `chroma_db/` to `.gitignore` because it stores local index files.
