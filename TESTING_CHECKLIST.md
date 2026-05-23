# AI Workflow Automation Sidecar - Testing & Verification Checklist

## 📋 Pre-Deployment Testing Checklist

### Phase 1: Environment Setup ✓ Verify

- [ ] Python 3.9+ installed (`python --version`)
- [ ] PostgreSQL running (`psql --version`)
- [ ] n8n running on http://localhost:5678
- [ ] All dependencies installed (`pip list | grep -E "fastapi|sqlalchemy"`)
- [ ] `.env` file created with all required variables
- [ ] `setup_verification.py` passes all checks

```bash
python setup_verification.py
# Expected: ✅ Setup verification PASSED!
```

---

### Phase 2: Database Setup ✓ Verify

- [ ] Database connection working

```bash
psql $DATABASE_URL -c "SELECT 1;"
# Expected: Returns "1"
```

- [ ] Tickets table created

```bash
psql $DATABASE_URL -c "\dt tickets"
# Expected: Lists tickets table
```

- [ ] Indexes created

```bash
psql $DATABASE_URL -c "\di" | grep tickets
# Expected: Shows indexes on tickets table
```

- [ ] Tables have proper columns

```bash
psql $DATABASE_URL -c "\d tickets"
# Expected: Lists all columns (ticket_id, user_id, issue, category, priority, assigned_team, status, etc)
```

---

### Phase 3: Backend API Tests ✓ Verify

#### 3.1 Health Check

```bash
curl http://localhost:8000/
# Expected: Returns {"message": "API is running"}
```

#### 3.2 Authentication

```bash
# Get JWT token (via Google OAuth)
# Then use in headers below

TOKEN="your-jwt-token-here"
```

#### 3.3 Create Ticket Endpoint

```bash
# Test with valid issue (10-5000 characters)
curl -X POST http://localhost:8000/api/tickets/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"issue": "Login button not working on mobile devices"}'

# Expected response:
# {
#   "ticket_id": "TICK-XXXXX",
#   "category": "bug",
#   "priority": "high",
#   "assigned_team": "frontend",
#   "status": "open",
#   "created_at": "2024-05-18T10:30:00"
# }
```

- [ ] Returns 200 OK
- [ ] ticket_id is generated correctly
- [ ] category is extracted
- [ ] priority is extracted
- [ ] assigned_team is extracted
- [ ] status defaults to "open"
- [ ] created_at timestamp is set

#### 3.4 Create Ticket - Validation Tests

```bash
# Test: Issue too short (should fail)
curl -X POST http://localhost:8000/api/tickets/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"issue": "short"}'

# Expected: 400 Bad Request
```

- [ ] Returns 400 for issue < 10 chars
- [ ] Returns 400 for issue > 5000 chars
- [ ] Returns 401 for missing token
- [ ] Returns 401 for invalid token

#### 3.5 List Tickets Endpoint

```bash
curl -X GET http://localhost:8000/api/tickets \
  -H "Authorization: Bearer $TOKEN"

# Expected: Returns array of tickets
# [
#   {
#     "id": 1,
#     "ticket_id": "TICK-XXXXX",
#     "issue": "...",
#     "category": "...",
#     "priority": "...",
#     "assigned_team": "...",
#     "status": "open",
#     "created_at": "..."
#   }
# ]
```

- [ ] Returns 200 OK
- [ ] Returns array of tickets
- [ ] Only returns user's own tickets
- [ ] Ordered by created_at DESC
- [ ] Includes all ticket fields

#### 3.6 Get Single Ticket Endpoint

```bash
curl -X GET http://localhost:8000/api/tickets/TICK-XXXXX \
  -H "Authorization: Bearer $TOKEN"

# Expected: Returns single ticket object
```

- [ ] Returns 200 OK for valid ticket_id
- [ ] Returns 404 for non-existent ticket_id
- [ ] Only returns if user owns ticket
- [ ] Includes all ticket fields

#### 3.7 Backend Security Tests

```bash
# Test: Missing JWT token
curl -X GET http://localhost:8000/api/tickets

# Expected: 403 Forbidden (or 401 Unauthorized)
```

```bash
# Test: Invalid JWT token
curl -X GET http://localhost:8000/api/tickets \
  -H "Authorization: Bearer invalid-token"

# Expected: 403 Forbidden
```

```bash
# Test: User cannot access other user's tickets
# (Requires creating tickets as different users)

# Expected: 404 or 403 when accessing other user's ticket
```

- [ ] Rejects requests without JWT
- [ ] Rejects requests with invalid JWT
- [ ] Prevents user from accessing other users' tickets
- [ ] JWT expiration is enforced

---

### Phase 4: n8n Workflow Tests ✓ Verify

#### 4.1 Workflow Import

- [ ] `n8n_workflows/ticket_automation.json` file exists
- [ ] Workflow imported successfully to n8n
- [ ] All 9 nodes present:
  1. [ ] webhook_trigger
  2. [ ] validate_secret
  3. [ ] extract_fields
  4. [ ] ai_agent_extract_metadata
  5. [ ] parse_ai_response
  6. [ ] generate_ticket_id
  7. [ ] store_in_postgresql
  8. [ ] send_gmail_confirmation
  9. [ ] respond_to_webhook

#### 4.2 Credentials Configuration

- [ ] OpenAI API key credential configured
- [ ] PostgreSQL connection credential configured
- [ ] Gmail credential configured (OAuth or app password)
- [ ] All credentials tested successfully

#### 4.3 Workflow Activation

- [ ] Workflow toggled to "Active" state
- [ ] Webhook URL displayed and accessible
- [ ] Webhook path is `/webhook/ticket-automation`

#### 4.4 Manual Webhook Test

```bash
curl -X POST http://localhost:5678/webhook/ticket-automation \
  -H "X-Webhook-Secret: $(echo $N8N_WEBHOOK_SECRET)" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-001",
    "user_email": "test@example.com",
    "user_name": "Test User",
    "issue": "Test ticket from webhook"
  }'

# Expected: Returns JSON with success=true and ticket_id
```

- [ ] Webhook accepts POST requests
- [ ] Secret validation works
- [ ] Returns JSON response
- [ ] Response includes ticket_id
- [ ] Workflow execution logged

#### 4.5 Workflow Node Testing

- [ ] Secret validation node rejects invalid secret
- [ ] AI Agent node makes API call to OpenAI
- [ ] JSON parsing handles both plain JSON and markdown-wrapped
- [ ] Ticket ID generation creates unique IDs
- [ ] PostgreSQL insert successful
- [ ] Gmail node sends email

#### 4.6 Error Handling

```bash
# Test: Invalid webhook secret
curl -X POST http://localhost:5678/webhook/ticket-automation \
  -H "X-Webhook-Secret: wrong-secret" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Expected: 401 Unauthorized
```

- [ ] Invalid secret returns 401
- [ ] Missing required fields returns error
- [ ] AI Agent failures are logged
- [ ] Database errors are logged
- [ ] Gmail errors are logged

---

### Phase 5: Frontend Component Tests ✓ Verify

#### 5.1 TicketForm Component

```javascript
// In browser console at http://localhost:5173/tickets
```

- [ ] Form renders without errors
- [ ] Textarea is visible
- [ ] Character counter visible
- [ ] Progress bar visible
- [ ] Submit button visible and disabled initially

#### 5.2 TicketForm Validation

- [ ] Typing updates character count in real-time
- [ ] Character count shows "X / 5000" format
- [ ] Progress bar fills as characters added
- [ ] Submit button enabled when 10+ characters
- [ ] Submit button disabled when > 5000 characters
- [ ] Progress bar color changes (red < 10, green >= 10)

#### 5.3 TicketForm Submission

- [ ] Clicking submit shows loading spinner
- [ ] Button disabled during submission
- [ ] Success message appears after creation
- [ ] Form clears after success
- [ ] onTicketCreated callback called with ticket data

#### 5.4 TicketForm Error Handling

- [ ] Network error shows error message
- [ ] n8n error shows error message
- [ ] Database error shows error message
- [ ] Error message dismissible
- [ ] Can retry submission after error

#### 5.5 TicketList Component

- [ ] List renders without errors
- [ ] Fetches tickets from API
- [ ] Displays each ticket as a card
- [ ] Shows loading spinner while fetching
- [ ] Shows error message if fetch fails
- [ ] Shows empty state if no tickets

#### 5.6 TicketList Filtering

- [ ] Status filter dropdown visible
- [ ] Options: All, Open, In Progress, Resolved, Closed
- [ ] Clicking filter updates displayed tickets
- [ ] Default filter is "All"

#### 5.7 TicketList Sorting

- [ ] Priority sort dropdown visible
- [ ] Options: All, Critical, High, Medium, Low
- [ ] Sorting updates card display order
- [ ] Critical tickets shown first
- [ ] Low priority shown last

#### 5.8 TicketList Card Display

Each card shows:
- [ ] Ticket ID (e.g., "TICK-001")
- [ ] Category icon (🐛 for bug, ✨ for feature, etc)
- [ ] Issue preview (first 100 characters)
- [ ] Category badge
- [ ] Priority badge (colored)
- [ ] Status badge (colored)
- [ ] Assigned team
- [ ] Created timestamp
- [ ] Responsive layout (1 col mobile, 3 col desktop)

#### 5.9 TicketList Responsive Design

```javascript
// Test at different viewport sizes
```

- [ ] Mobile (320px): 1 column, stacked
- [ ] Tablet (768px): 2 columns
- [ ] Desktop (1024px+): 3 columns
- [ ] Touch interactions work on mobile
- [ ] Scrolling works smoothly

#### 5.10 Tickets Page Integration

- [ ] Page renders without errors
- [ ] Form on left side
- [ ] List on right side
- [ ] Creating ticket updates list
- [ ] Success message appears after creation
- [ ] List refreshes automatically
- [ ] Success message disappears after 5 seconds

#### 5.11 Animations

- [ ] Form submission shows smooth loading
- [ ] Success message fades in
- [ ] Ticket cards have staggered entrance animation
- [ ] Filter/sort changes animate smoothly
- [ ] No animation jank or stuttering

#### 5.12 Accessibility

- [ ] Form inputs have labels
- [ ] Character counter readable by screen readers
- [ ] Buttons have descriptive text
- [ ] Error messages announced to screen readers
- [ ] Color not sole differentiator (badges have icons too)
- [ ] Keyboard navigation works (Tab, Enter, etc)

---

### Phase 6: End-to-End Integration Tests ✓ Verify

#### 6.1 Complete Workflow

```
User submits issue → React form validation → API request → FastAPI validation 
→ n8n webhook call → Secret validation → AI extraction → Database insert 
→ Email sent → Response to React → Show success
```

Steps to verify:

1. [ ] Navigate to http://localhost:5173/tickets (React)
2. [ ] Log in via Google OAuth
3. [ ] Type issue: "Payment button not responding on checkout"
4. [ ] Click Submit
5. [ ] Observe:
   - [ ] Loading spinner shows
   - [ ] Success message appears
   - [ ] Ticket ID generated (TICK-XXXXX)
   - [ ] Category extracted (bug, feature, etc)
   - [ ] Priority extracted (low, medium, high, critical)
   - [ ] Team assigned (frontend, backend, etc)
6. [ ] Check backend logs

```bash
# In backend terminal
# Should see: "Ticket created: TICK-XXXXX"
# Should see: "n8n response: {...}"
```

7. [ ] Check n8n logs

```bash
# In n8n UI → Execution History
# Should see workflow executed successfully
# Should see AI agent output
# Should see database insert
# Should see email sent
```

8. [ ] Check email inbox

```
Should receive email:
Subject: "Ticket Created: TICK-XXXXX"
Contains: ticket_id, category, priority, assigned_team
```

9. [ ] Check database

```bash
psql $DATABASE_URL -c "SELECT ticket_id, category, priority, assigned_team FROM tickets ORDER BY created_at DESC LIMIT 1;"
```

10. [ ] Check React list

```
Navigate to ticket list
Should see new ticket at top
Should show correct category, priority, team
```

#### 6.2 Multiple Tickets

- [ ] Create 3-4 different issues
- [ ] Each generates unique ticket_id
- [ ] Each extracts different metadata
- [ ] All appear in ticket list
- [ ] List shows most recent first

#### 6.3 Filtering & Sorting

```
With multiple tickets created:
```

- [ ] Filter by status shows only matching tickets
- [ ] Sort by priority shows critical first
- [ ] Combining filters/sorts works correctly
- [ ] Can switch between filters without errors

#### 6.4 Data Consistency

- [ ] Data in React matches database
- [ ] Data in React matches email
- [ ] n8n_execution_id tracked in database
- [ ] Timestamps are consistent across systems

---

### Phase 7: Load & Stress Tests ✓ Verify

#### 7.1 Concurrent Requests

```bash
# Create 5 tickets simultaneously
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/tickets/create \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"issue\": \"Concurrent test issue $i Lorem ipsum dolor sit amet consectetur\"}" &
done
wait
```

- [ ] All 5 tickets created successfully
- [ ] No duplicate ticket_ids
- [ ] No database errors
- [ ] All emails sent

#### 7.2 High Volume List Fetching

```bash
# Fetch tickets list repeatedly
for i in {1..10}; do
  curl -X GET http://localhost:8000/api/tickets \
    -H "Authorization: Bearer $TOKEN"
done
```

- [ ] All requests return 200 OK
- [ ] Response time remains consistent
- [ ] No memory leaks
- [ ] No database connection exhaustion

#### 7.3 Long-Running Stability

- [ ] Service stable after 1 hour of operation
- [ ] No memory growth
- [ ] No database connection leaks
- [ ] Email queues not blocking

---

### Phase 8: Security Tests ✓ Verify

#### 8.1 Authentication

```bash
# Test without token
curl -X GET http://localhost:8000/api/tickets
# Expected: 403/401 Unauthorized

# Test with expired token
curl -X GET http://localhost:8000/api/tickets \
  -H "Authorization: Bearer expired-token"
# Expected: 403/401 Unauthorized
```

- [ ] Missing token rejected
- [ ] Invalid token rejected
- [ ] Expired token rejected
- [ ] Can't create tickets without auth
- [ ] Can't view tickets without auth

#### 8.2 User Isolation

```bash
# Create two users, create tickets for each
# User A should NOT see User B's tickets
```

- [ ] User A cannot see User B's tickets
- [ ] User A cannot access User B's ticket details
- [ ] Query filters by user_id
- [ ] Database constraints enforce isolation

#### 8.3 Secret Validation

```bash
# Test n8n webhook with wrong secret
curl -X POST http://localhost:5678/webhook/ticket-automation \
  -H "X-Webhook-Secret: wrong-secret" \
  -d '...'
# Expected: 401 Unauthorized
```

- [ ] Wrong secret rejected
- [ ] Missing secret rejected
- [ ] Empty secret rejected
- [ ] Only valid secret accepted

#### 8.4 Input Validation

- [ ] XSS attempts in issue field sanitized
- [ ] SQL injection attempts prevented (ORM)
- [ ] Very long strings truncated/rejected
- [ ] Special characters handled correctly
- [ ] Unicode characters handled correctly

#### 8.5 CORS & Origin Validation

```bash
# Test from different origin
curl -X GET http://localhost:8000/api/tickets \
  -H "Origin: http://wrong-origin.com"
```

- [ ] CORS headers correct
- [ ] Only allowed origins accepted
- [ ] Preflight requests handled correctly

---

### Phase 9: Error Recovery & Resilience ✓ Verify

#### 9.1 Database Connection Loss

```bash
# Stop PostgreSQL, then restart
sudo systemctl stop postgresql
sudo systemctl start postgresql
```

- [ ] Connection error logged
- [ ] Service recovers after DB is back
- [ ] No data corruption
- [ ] Pending requests can retry

#### 9.2 n8n Unavailable

```bash
# Stop n8n, submit ticket
```

- [ ] Timeout error returned
- [ ] Error message shown in React
- [ ] User can retry
- [ ] No orphaned database records

#### 9.3 Gmail Unavailable

```bash
# Disable Gmail credentials
# Submit ticket
```

- [ ] Ticket still created
- [ ] Email error logged
- [ ] User notified
- [ ] Ticket status updated (pending email?)

#### 9.4 AI Agent Failure

```bash
# Disable OpenAI credentials
# Submit ticket
```

- [ ] Workflow logs error
- [ ] Response to FastAPI indicates failure
- [ ] FastAPI returns error to React
- [ ] User sees error message

---

### Phase 10: Performance Tests ✓ Verify

#### 10.1 Response Times

```bash
# Measure endpoint response times
time curl -X POST http://localhost:8000/api/tickets/create \
  -H "Authorization: Bearer $TOKEN" \
  -d '...'
```

- [ ] Create ticket: < 30 seconds (includes AI Agent)
- [ ] List tickets: < 1 second
- [ ] Get single ticket: < 500ms

#### 10.2 Database Query Performance

```bash
# Check query times in PostgreSQL logs
SELECT total_time, query FROM pg_stat_statements 
WHERE query LIKE '%tickets%' ORDER BY total_time DESC;
```

- [ ] Queries use indexes
- [ ] No sequential scans on large tables
- [ ] Query plans are efficient

#### 10.3 Frontend Performance

```javascript
// In browser console
const start = performance.now();
// Perform action
const end = performance.now();
console.log(`Time: ${end - start}ms`);
```

- [ ] Form submission: < 2 seconds
- [ ] List fetch: < 1 second
- [ ] Filter/sort: < 500ms
- [ ] No jank during animations

#### 10.4 Memory Usage

```bash
# Monitor backend memory
top -p $(pgrep -f "uvicorn")
```

- [ ] Stable memory usage
- [ ] No unbounded growth
- [ ] No memory leaks after 1000+ operations

---

## ✅ Final Verification Checklist

After completing all phases above, verify:

### Code Quality
- [ ] All imports resolve
- [ ] No TypeScript errors
- [ ] No Python syntax errors
- [ ] Linting passes (if configured)
- [ ] No console errors in browser

### Documentation
- [ ] WORKFLOW_AUTOMATION_GUIDE.md complete
- [ ] QUICK_START.md complete
- [ ] .env.example documented
- [ ] Code comments clear
- [ ] API endpoints documented

### Version Control
- [ ] All changes committed
- [ ] .env not in git (in .gitignore)
- [ ] No secrets in code
- [ ] No large files committed

### Production Readiness
- [ ] Environment variables externalized
- [ ] Error handling comprehensive
- [ ] Logging configured
- [ ] Monitoring ready
- [ ] Database backups configured
- [ ] Email service scaled
- [ ] Rate limiting ready
- [ ] CORS configured for production

### Sign-Off

- [ ] Backend Lead: Code quality ✓
- [ ] Frontend Lead: UI/UX ✓
- [ ] DevOps Lead: Deployment ready ✓
- [ ] Product: Feature complete ✓
- [ ] Security: Security audit passed ✓

---

## 📊 Test Results Summary

| Phase | Total Tests | Passed | Failed | Notes |
|-------|-------------|--------|--------|-------|
| 1. Setup | 5 | ☐ | ☐ | |
| 2. Database | 4 | ☐ | ☐ | |
| 3. API | 7 | ☐ | ☐ | |
| 4. n8n | 6 | ☐ | ☐ | |
| 5. Frontend | 12 | ☐ | ☐ | |
| 6. E2E | 4 | ☐ | ☐ | |
| 7. Load | 3 | ☐ | ☐ | |
| 8. Security | 5 | ☐ | ☐ | |
| 9. Resilience | 4 | ☐ | ☐ | |
| 10. Performance | 4 | ☐ | ☐ | |
| **TOTAL** | **54** | **☐** | **☐** | |

---

**Testing Date**: ____________
**Tested By**: ____________
**Status**: ☐ PASS  ☐ FAIL

**Issues Found**:
```
[List any issues found during testing]
```

**Sign-Off**:
- QA Lead: _____________ Date: _______
- Product: _____________ Date: _______
- DevOps: _____________ Date: _______
