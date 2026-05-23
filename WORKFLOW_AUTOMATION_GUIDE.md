# AI Workflow Automation Sidecar - Complete Implementation Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Component Breakdown](#component-breakdown)
4. [Setup Instructions](#setup-instructions)
5. [API Documentation](#api-documentation)
6. [Frontend Components](#frontend-components)
7. [n8n Workflow](#n8n-workflow)
8. [Security Rules](#security-rules)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The **AI Workflow Automation Sidecar** is a full-stack application that automates ticket creation using AI-powered workflow orchestration. Users submit issues in natural language, and the system automatically extracts category, priority, and team assignment.

### Key Features

- ✅ **Natural Language Issue Submission** - Users describe issues in plain English
- ✅ **AI-Powered Metadata Extraction** - GPT-4o extracts category, priority, team
- ✅ **Secure Architecture** - FastAPI acts as boundary; React never calls n8n
- ✅ **Workflow Automation** - n8n orchestrates entire process
- ✅ **Email Confirmations** - Users get Gmail confirmation with ticket ID
- ✅ **Database Persistence** - PostgreSQL/Supabase for ticket storage
- ✅ **Multi-threaded Chat** - Existing chat system remains unchanged
- ✅ **Responsive UI** - React components with Tailwind CSS

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /tickets Page (React)                               │  │
│  │  ├─ TicketForm.tsx (Submit issue)                    │  │
│  │  ├─ TicketList.tsx (View history)                    │  │
│  │  └─ Status badges + Filter UI                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓ HTTPS/JWT
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/tickets/create (POST)  ← React sends issue    │  │
│  │  ├─ Validates request                               │  │
│  │  ├─ Verifies JWT auth                               │  │
│  │  ├─ Calls n8n webhook (secret validation)           │  │
│  │  ├─ Stores response in PostgreSQL                   │  │
│  │  └─ Returns ticket to React                         │  │
│  │                                                      │  │
│  │  /api/tickets (GET)       ← React fetches list     │  │
│  │  /api/tickets/{id} (GET)  ← React gets detail      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                    ↓ Secure HTTP + Secret
┌─────────────────────────────────────────────────────────────┐
│                    n8n Workflow                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Webhook Trigger (receives from FastAPI)         │  │
│  │  2. Secret Validation                               │  │
│  │  3. Extract Fields                                  │  │
│  │  4. AI Agent (GPT-4o)                               │  │
│  │     └─ Extracts: category, priority, team           │  │
│  │  5. Parse AI Response                               │  │
│  │  6. Generate Ticket ID                              │  │
│  │  7. Store in PostgreSQL                             │  │
│  │  8. Send Gmail Confirmation                         │  │
│  │  9. Return structured response                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                    ↓ Database + Email
┌──────────────────────────┬──────────────────────────────────┐
│   PostgreSQL Database    │        Gmail API                 │
│  ┌────────────────────┐  │  ┌──────────────────────────┐   │
│  │ tickets table      │  │  │ Send confirmation email  │   │
│  │ - ticket_id        │  │  │ to user_email with       │   │
│  │ - user_id          │  │  │ ticket details           │   │
│  │ - issue            │  │  └──────────────────────────┘   │
│  │ - category         │  │                                  │
│  │ - priority         │  │                                  │
│  │ - assigned_team    │  │                                  │
│  │ - status           │  │                                  │
│  │ - timestamps       │  │                                  │
│  └────────────────────┘  │                                  │
└──────────────────────────┴──────────────────────────────────┘
```

---

## Component Breakdown

### Backend Components

#### 1. **models.py** (Database Models)
```python
class Ticket(Base):
    ticket_id: str          # TICK-001, TICK-002, etc
    user_id: int            # Foreign key to users
    issue: str              # Original issue description
    category: str           # Extracted: bug, feature, support, etc
    priority: str           # Extracted: low, medium, high, critical
    assigned_team: str      # Extracted: frontend, backend, devops, etc
    status: str             # open, in_progress, resolved, closed
    n8n_execution_id: str   # Track which n8n workflow created it
    created_at: datetime
    updated_at: datetime
```

#### 2. **routes/tickets.py** (API Endpoints)
```
POST   /api/tickets/create         Create ticket (calls n8n)
GET    /api/tickets                List user's tickets
GET    /api/tickets/{ticket_id}    Get specific ticket
```

#### 3. **services/ticket_automation.py** (Service Layer)
- `TicketAutomationService` - Handles n8n webhook calls
- `TicketValidator` - Validates issue format
- `parse_n8n_response()` - Normalizes n8n output

#### 4. **main.py** (App Setup)
- Registers tickets router
- Includes new Ticket model in database creation

### Frontend Components

#### 1. **pages/Tickets.tsx** (Main Page)
- Container component for ticket system
- Coordinates form and list
- Manages refresh trigger

#### 2. **components/TicketForm.tsx** (Form)
- Issue input textarea
- Character counter with progress bar
- Real-time validation
- Loading state during API call
- Error/success messages

#### 3. **components/TicketList.tsx** (List)
- Displays all user tickets
- Filter by status
- Sort by priority
- Status badges with colors
- Responsive grid layout

### n8n Workflow

The workflow is configured in `n8n_workflows/ticket_automation.json` with these nodes:

1. **Webhook Trigger** - Receives POST from FastAPI
2. **Validate Secret** - Checks X-Webhook-Secret header
3. **Extract Fields** - Normalizes incoming data
4. **AI Agent** - GPT-4o extracts metadata
5. **Parse Response** - Converts JSON from AI
6. **Generate Ticket ID** - Creates TICK-000001 format
7. **Store in PostgreSQL** - Inserts ticket record
8. **Send Gmail** - Sends confirmation email
9. **Respond to Webhook** - Returns result to FastAPI

---

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL 12+ (or Supabase)
- n8n running on http://localhost:5678
- Google OAuth credentials
- Gmail credentials or app password
- OpenAI API key

### Step 1: Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp ../.env.example .env

# Edit .env with your values:
# - DATABASE_URL: Your PostgreSQL connection
# - N8N_WEBHOOK_URL: http://localhost:5678/webhook/ticket-automation
# - N8N_WEBHOOK_SECRET: Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# - GMAIL_EMAIL / GMAIL_PASSWORD
# - OPENAI_API_KEY
# - GOOGLE_CLIENT_ID / SECRET

# Run database migrations
alembic upgrade head  # if migrations exist
# OR migrations happen automatically on startup via:
# Base.metadata.create_all()

# Start backend
python main.py
# OR: uvicorn app.main:app --reload --port 8000
```

### Step 2: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Open http://localhost:5173
# Navigate to /tickets page
```

### Step 3: n8n Workflow Setup

1. **Export workflow**: Copy `n8n_workflows/ticket_automation.json`
2. **Import to n8n**:
   - Open n8n UI at http://localhost:5678
   - Click "Create New" → "From File"
   - Upload `ticket_automation.json`
3. **Configure credentials**:
   - Set OpenAI API key credential
   - Set PostgreSQL connection credential
   - Set Gmail credential (OAuth or app password)
4. **Set environment variables**:
   - `N8N_WEBHOOK_SECRET` - Must match FastAPI's env var
5. **Activate workflow**: Toggle "Active" to ON
6. **Get webhook URL**: Should be `http://localhost:5678/webhook/ticket-automation`

### Step 4: Verify Setup

```bash
# Test API endpoint
curl -X POST http://localhost:8000/api/tickets/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"issue": "Login button not working on mobile"}'

# Expected response:
{
  "ticket_id": "TICK-12345",
  "category": "bug",
  "priority": "high",
  "assigned_team": "frontend",
  "status": "open",
  "created_at": "2024-05-18T10:30:00"
}
```

---

## API Documentation

### POST /api/tickets/create

**Description**: Create a new ticket via AI workflow

**Request**:
```json
{
  "issue": "Login page is not loading on mobile devices, shows blank screen after tap"
}
```

**Request Headers**:
- `Authorization: Bearer {jwt_token}`
- `Content-Type: application/json`

**Response** (200 OK):
```json
{
  "ticket_id": "TICK-001",
  "category": "bug",
  "priority": "high",
  "assigned_team": "frontend",
  "status": "open",
  "created_at": "2024-05-18T10:30:00"
}
```

**Errors**:
- `400 Bad Request` - Issue too short or too long
- `401 Unauthorized` - Missing/invalid JWT
- `500 Internal Server Error` - n8n workflow failed

### GET /api/tickets

**Description**: Get list of all user's tickets

**Request Headers**:
- `Authorization: Bearer {jwt_token}`

**Query Parameters**:
- `status` (optional): Filter by status (open, in_progress, resolved, closed)
- `sort` (optional): Sort by created_at or priority

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "ticket_id": "TICK-001",
    "issue": "Login page is not loading...",
    "category": "bug",
    "priority": "high",
    "assigned_team": "frontend",
    "status": "open",
    "created_at": "2024-05-18T10:30:00"
  }
]
```

### GET /api/tickets/{ticket_id}

**Description**: Get specific ticket details

**Request Headers**:
- `Authorization: Bearer {jwt_token}`

**Response** (200 OK):
```json
{
  "id": 1,
  "ticket_id": "TICK-001",
  "issue": "Login page is not loading...",
  "category": "bug",
  "priority": "high",
  "assigned_team": "frontend",
  "status": "open",
  "created_at": "2024-05-18T10:30:00"
}
```

---

## Frontend Components

### TicketForm.tsx

**Props**:
- `onTicketCreated?: (ticket: any) => void` - Callback when ticket created
- `onError?: (error: string) => void` - Callback on error

**Features**:
- Textarea with min 10, max 5000 characters
- Real-time character counter
- Visual progress bar
- Submit button disables until valid
- Shows error/success messages
- Loading spinner during API call

**Usage**:
```tsx
<TicketForm 
  onTicketCreated={(ticket) => console.log('Created:', ticket)}
  onError={(error) => console.error(error)}
/>
```

### TicketList.tsx

**Props**:
- `refreshTrigger?: number` - Increment to refresh list
- `onTicketSelect?: (ticket: Ticket) => void` - Click handler

**Features**:
- Fetches tickets from `/api/tickets`
- Filter by status (all, open, in_progress, resolved, closed)
- Sort by priority or date
- Category icons (🐛 for bug, ✨ for feature, etc.)
- Priority color coding (critical=red, high=orange, etc.)
- Status color coding (open=blue, resolved=green, etc.)
- Responsive grid (1 col mobile, 3 col desktop)
- Loading/error states

### Tickets.tsx (Page)

**Features**:
- Combined form and list on single page
- Side-by-side layout (1 col mobile, 3 col desktop)
- Sticky form on desktop
- Success notification after creation
- Refresh list after ticket created
- Educational info section about workflow

---

## n8n Workflow

### Flow

```
Webhook (FastAPI sends issue)
  ↓
Validate Secret Header
  ├─ Valid: Continue
  └─ Invalid: Respond with 401
  ↓
Extract Fields (normalize payload)
  ↓
AI Agent (GPT-4o)
  "Analyze this issue and extract JSON:
   {category, priority, assigned_team, summary}"
  ↓
Parse AI Response
  (Handle JSON parsing, extract from markdown if needed)
  ↓
Generate Ticket ID
  (Create TICK-000001 format)
  ↓
Store in PostgreSQL
  INSERT INTO tickets (ticket_id, user_id, issue, category, ...)
  ↓
Send Gmail
  To: user_email
  Subject: "Ticket Created: TICK-001"
  Body: HTML with ticket details
  ↓
Respond to Webhook
  Return {success: true, ticket_id: "TICK-001", ...}
```

### Node Details

**AI Agent Prompt**:
```
You are a ticket classification AI agent. Analyze the following issue and extract metadata.

Issue:
{issue_from_user}

Respond with ONLY valid JSON (no markdown, no code blocks):
{
  "category": "one of: bug, feature, support, documentation, infrastructure, performance, security, ui, backend, api, database",
  "priority": "one of: low, medium, high, critical",
  "assigned_team": "the team that should handle this (e.g., frontend, backend, devops, security)",
  "summary": "2-3 sentence summary of the issue"
}
```

---

## Security Rules

### 🔒 React Cannot Call n8n Directly

- ❌ React NEVER makes requests to n8n
- ✅ All n8n calls go through FastAPI
- ✅ FastAPI validates secret before calling n8n
- ✅ React only knows about FastAPI endpoints

### 🔐 Secret Validation

- n8n workflow validates `X-Webhook-Secret` header
- FastAPI sends this header when calling n8n
- Secret stored in environment variables (not committed to git)
- Both FastAPI and n8n must have matching secret

### 🛡️ JWT Authentication

- All `/api/tickets/*` endpoints require valid JWT
- JWT obtained via Google OAuth login
- Token includes user_id for data isolation
- Users can only see their own tickets

### 🔒 Data Isolation

- Queries always filter by `user_id`
- Users cannot access other users' tickets
- Database enforces foreign key constraints
- SQL injection prevented via SQLAlchemy ORM

---

## Troubleshooting

### Issue: "Failed to create ticket"

**Causes**:
1. n8n workflow not running
2. Webhook URL not reachable
3. Secret mismatch between FastAPI and n8n
4. Database connection failed

**Solutions**:
```bash
# Check n8n is running
curl http://localhost:5678/api/v1/workflows

# Check webhook secret matches
echo $N8N_WEBHOOK_SECRET
# Compare with n8n env var

# Check database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check FastAPI logs
# Look for error details in backend output
```

### Issue: "Unauthorized - invalid webhook secret"

**Cause**: Secret in FastAPI .env doesn't match n8n

**Solution**:
```bash
# Generate new secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update FastAPI .env
N8N_WEBHOOK_SECRET=new-secret-value

# Update n8n environment variable or workflow
# Restart both services
```

### Issue: AI Agent returning invalid JSON

**Cause**: GPT-4o response includes markdown code blocks

**Solution**: The `Parse AI Response` node handles this:
```javascript
// If JSON is wrapped in markdown, extract it
const jsonMatch = response.match(/\{[^{}]*\}/s);
if (jsonMatch) {
  parsed = JSON.parse(jsonMatch[0]);
}
```

### Issue: Gmail not sending confirmation emails

**Cause**: Gmail credentials invalid or 2FA enabled

**Solution**:
```bash
# For Gmail with 2FA enabled, use App Password:
# 1. Enable 2FA on Google Account
# 2. Create App Password: https://myaccount.google.com/apppasswords
# 3. Use the generated 16-character password in .env
# 4. Update n8n Gmail credentials

# For OAuth:
# 1. Download credentials JSON from Google Cloud Console
# 2. Set GMAIL_CREDENTIALS_JSON in .env
# 3. Configure n8n Gmail node with OAuth
```

### Issue: Ticket not appearing in database

**Cause**: PostgreSQL insert failed

**Solution**:
```sql
-- Check if tickets table exists
\dt tickets

-- Check table structure
\d tickets

-- Check for insert errors in n8n logs
-- Look for "Error in PostgreSQL node" messages
```

---

## Integration with Existing Functionality

### ✅ No Breaking Changes

- Existing chat system (`/api/chat`) unchanged
- Existing upload system (`/api/uploads`) unchanged
- Existing authentication (`/api/auth`) unchanged
- All existing routes continue working
- Database only adds new `tickets` table

### 📡 Sharing Database & Auth

- Tickets use same `users` table and JWT auth
- Users identified by `current_user` (shared)
- Same database connection string (just adds table)

### 🔄 Future Integration

- Could trigger chat when ticket created
- Could add ticket-related chat context
- Could allow natural language ticket queries
- All without modifying existing systems

---

## Production Deployment

### Environment Variables (Production)

```bash
# Must set before deploying
N8N_WEBHOOK_URL=https://n8n.yourdomain.com/webhook/ticket-automation
N8N_WEBHOOK_SECRET=generate-new-secret-for-production
DATABASE_URL=postgresql://...prod...
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...prod...
GMAIL_EMAIL=support@yourdomain.com
```

### Deployment Checklist

- [ ] All environment variables set
- [ ] SSL/TLS enabled for all endpoints
- [ ] Database backups configured
- [ ] n8n auto-activates workflow on startup
- [ ] Monitoring/alerting for failed workflows
- [ ] Email rate limiting configured
- [ ] CORS configured for production domains
- [ ] JWT secret rotation policy in place

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Check n8n workflow logs
3. Check FastAPI backend logs
4. Check PostgreSQL query logs
5. Verify all environment variables are set
