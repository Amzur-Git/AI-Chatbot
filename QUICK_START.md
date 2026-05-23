# AI Workflow Automation Sidecar - Quick Start

## 📖 5-Minute Setup

### 1. Configure Environment

```bash
# Copy .env template
cp .env.example .env

# Edit and fill in:
# - N8N_WEBHOOK_URL=http://localhost:5678/webhook/ticket-automation
# - N8N_WEBHOOK_SECRET=your-secret-key (generate: python -c "import secrets; print(secrets.token_urlsafe(32))")
# - DATABASE_URL=postgresql://user:pass@localhost/db
# - OPENAI_API_KEY=sk-...
# - GOOGLE_CLIENT_ID=...
# - GMAIL_EMAIL=...
# - GMAIL_PASSWORD=...

nano .env
```

### 2. Run Verification

```bash
python setup_verification.py
```

Expected output: ✅ Setup verification PASSED!

### 3. Start Services (in separate terminals)

**Terminal 1 - Backend**:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend**:
```bash
cd frontend
npm run dev
```

**Terminal 3 - n8n** (already running):
```bash
# If not running, start from n8n installation
npm start
```

### 4. Import n8n Workflow

1. Open n8n UI: http://localhost:5678
2. Click "Create New" → "From File"
3. Upload `n8n_workflows/ticket_automation.json`
4. Click each node and configure credentials:
   - **AI Agent node**: OpenAI API key
   - **PostgreSQL node**: Database connection
   - **Gmail node**: Gmail OAuth or app password
5. Toggle workflow to "Active"
6. Copy webhook URL from "Listen" section

### 5. Test End-to-End

1. Open http://localhost:5173/tickets (React frontend)
2. Log in (Google OAuth)
3. Enter an issue: "Login button not working on mobile"
4. Submit
5. Check for:
   - ✅ Success message in React
   - ✅ Email confirmation sent
   - ✅ Ticket visible in ticket list
   - ✅ Backend logs show "ticket created"
   - ✅ n8n logs show workflow execution

---

## 📁 File Structure

```
├── .env.example              ← Template for environment variables
├── n8n_workflows/            ← n8n workflow files
│   └── ticket_automation.json ← Main workflow (import to n8n)
├── WORKFLOW_AUTOMATION_GUIDE.md ← Full documentation
├── setup_verification.py      ← Verify setup before running
├── backend/
│   ├── app/
│   │   ├── models.py          ← Extended with Ticket model
│   │   ├── main.py            ← Registers tickets routes
│   │   ├── routes/
│   │   │   └── tickets.py     ← Ticket API endpoints
│   │   └── services/
│   │       └── ticket_automation.py ← n8n integration
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx            ← Updated with /tickets route
│   │   ├── components/
│   │   │   ├── TicketForm.tsx   ← Issue submission form
│   │   │   └── TicketList.tsx   ← View ticket history
│   │   └── pages/
│   │       └── Tickets.tsx      ← Main tickets page
│   └── package.json
```

---

## 🔌 API Endpoints Quick Reference

```bash
# Create ticket (POST)
curl -X POST http://localhost:8000/api/tickets/create \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"issue": "Your issue here"}'

# List tickets (GET)
curl -X GET http://localhost:8000/api/tickets \
  -H "Authorization: Bearer $JWT"

# Get specific ticket (GET)
curl -X GET http://localhost:8000/api/tickets/TICK-001 \
  -H "Authorization: Bearer $JWT"
```

---

## 🛠️ Common Tasks

### Generate Webhook Secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Check Backend Logs

```bash
cd backend
tail -f logs/app.log  # if enabled
```

### Check n8n Workflow Status

1. Open http://localhost:5678
2. Click workflow
3. View "Execution History"

### Test n8n Webhook

```bash
curl -X POST http://localhost:5678/webhook/ticket-automation \
  -H "X-Webhook-Secret: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req-123",
    "user_email": "user@example.com",
    "user_name": "John",
    "issue": "Fix login button"
  }'
```

### Debug Database Connection

```bash
# Test PostgreSQL connection
psql $DATABASE_URL -c "SELECT version();"

# List tables
psql $DATABASE_URL -c "\dt"

# View tickets
psql $DATABASE_URL -c "SELECT ticket_id, category, priority FROM tickets LIMIT 10;"
```

---

## 📊 Architecture Overview

```
React UI (localhost:5173)
    ↓ Submit issue
FastAPI Backend (localhost:8000)
    ↓ Call webhook (secret validation)
n8n Workflow (localhost:5678)
    ↓ Process with AI
PostgreSQL
    ↓ Store ticket
Gmail
    ↓ Send confirmation
```

---

## ⚠️ Troubleshooting

### "Failed to create ticket"

```bash
# 1. Check n8n is running
curl http://localhost:5678/api/v1/workflows

# 2. Check webhook URL
echo $N8N_WEBHOOK_URL

# 3. Check secret matches
echo $N8N_WEBHOOK_SECRET
# Compare with n8n env var
```

### "Unauthorized - invalid webhook secret"

```bash
# Generate new secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update both .env files
nano .env
# Update N8N_WEBHOOK_SECRET

# Restart services
```

### Email not sending

```bash
# Check Gmail credentials
echo $GMAIL_EMAIL
echo $GMAIL_PASSWORD  # (don't commit!)

# For 2FA enabled accounts, use App Password instead:
# https://myaccount.google.com/apppasswords
```

---

## 📚 Documentation

- **Full Guide**: See [WORKFLOW_AUTOMATION_GUIDE.md](WORKFLOW_AUTOMATION_GUIDE.md)
- **API Docs**: See WORKFLOW_AUTOMATION_GUIDE.md → API Documentation
- **Component Docs**: See WORKFLOW_AUTOMATION_GUIDE.md → Frontend Components
- **Security**: See WORKFLOW_AUTOMATION_GUIDE.md → Security Rules

---

## 🎯 Next Steps

1. ✅ Configure environment
2. ✅ Run verification
3. ✅ Start services
4. ✅ Import n8n workflow
5. ✅ Test end-to-end
6. ⏭️ Deploy to production
7. ⏭️ Add monitoring/alerting
8. ⏭️ Integrate with existing chat system

---

## 💡 Tips

- Keep `.env` out of git (add to `.gitignore`)
- Use different secrets for dev/prod
- Enable n8n logging for debugging
- Monitor email delivery (Gmail API quota)
- Set up database backups
- Scale n8n for high volume

---

## 🆘 Need Help?

1. Read WORKFLOW_AUTOMATION_GUIDE.md
2. Check logs in backend and n8n UI
3. Run `setup_verification.py`
4. Review troubleshooting section above

**Happy automating!** 🚀
