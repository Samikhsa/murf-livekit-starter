# Day 8 — Track Call Success Rates & Call Analytics Dashboard

A complete runbook and overview for Day 8 of the **10 Days of Voice Agents** challenge.

**Track:** Local Commerce — **ShopMitra**  
**Use Case:** *Call Success Rate Tracking & Real-Time Analytics Dashboard*

---

## What Was Built

| Component | File | Description |
|-----------|------|-------------|
| Analytics Database | `backend/src/database.py` | `call_analytics` table, `record_call_start()`, `record_call_end()`, `get_call_stats()`, `list_recent_calls()` |
| Analytics HTTP API | `backend/src/analytics_api.py` | aiohttp server routes (`/api/calls/stats`, `/api/calls`) on port 8765 |
| Session Lifecycle Tracking | `backend/src/agent.py` | Auto-detects call start/end, tracks duration, assigns call outcomes & failure taxonomy |
| Analytics Dashboard | `frontend/app/dashboard/page.tsx` | Next.js dark-mode dashboard with KPI metric cards, failure breakdown, and live call logs |
| Navigation Header | `frontend/app/layout.tsx` | Global top navigation bar linking Store Front, Escalations, and Analytics Dashboard |

---

## Architecture

```
User / Caller (Browser or SIP)
     │
     ▼
LiveKit Agent (backend/src/agent.py)
     ├─ On Session Start ──> database.record_call_start(call_id, channel)
     │                                └─ Inserts row into `call_analytics` (status='pending')
     │
     ├─ During Call ───────> Agent handles voice loop (ordering, escalation, restock)
     │                                └─ Sets outcome flag based on task completion / escalation / tools
     │
     └─ On Session End ────> database.record_call_end(call_id, outcome, failure_type, duration)
                                      └─ Updates `call_analytics` (status='success'|'failed')

                                ┌───────────────────────────────────────────────┐
                                │             HTTP API (Port 8765)              │
                                │  GET /api/calls/stats   GET /api/calls        │
                                └───────────────────────┬───────────────────────┘
                                                        │
                                                        ▼
                                       Next.js Dashboard (/dashboard)
                                       - Total Calls & Success Rate %
                                       - Failure Taxonomy Breakdown
                                       - Privacy-Preserving Call History
```

---

## Call Success & Failure Taxonomy

Every call is classified strictly on session end:

| Outcome | Trigger Condition | Failure Type |
|---------|-------------------|--------------|
| **SUCCESS** | Order placed, escalation ticket generated, query resolved, or successful restock confirmation | `None` |
| **FAILED** | Caller hung up within 5 seconds without interaction | `user_hangup` |
| **FAILED** | User request could not be completed / unresolved issue | `incomplete_task` |
| **FAILED** | Exception or tool execution error occurred | `tool_error` |
| **FAILED** | No audio / response detected from caller | `no_response` |

---

## Privacy-First Data Model

The `call_analytics` table intentionally stores **zero PII**:

- **No** caller names
- **No** phone numbers
- **No** email addresses
- **No** transcript logs or audio recordings

### Table Schema (`call_analytics`)

```sql
CREATE TABLE IF NOT EXISTS call_analytics (
    call_id          TEXT PRIMARY KEY,
    room_name        TEXT NOT NULL,
    channel          TEXT NOT NULL DEFAULT 'browser', -- 'browser' or 'sip'
    outcome          TEXT NOT NULL DEFAULT 'pending', -- 'success', 'failed', 'pending'
    failure_type     TEXT,                            -- 'user_hangup', 'incomplete_task', 'tool_error', 'no_response'
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    started_at       TEXT NOT NULL,
    ended_at         TEXT
);
```

---

## HTTP Analytics API

The analytics API runs alongside the escalation server on port `8765`:

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/calls/stats` | `GET` | Aggregated KPI stats | `{ total, successful, failed, pending, success_rate }` |
| `/api/calls` | `GET` | List recent call sessions | `{ calls: [...], total }` |
| `/api/calls` | `POST` | Record session start | Created call object |
| `/api/calls/<call_id>` | `PATCH` | Update session end outcome | Updated call object |

---

## Dashboard Interface

Visit: `http://localhost:3000/dashboard`

### Features:
1. **KPI Stat Cards:** Total Calls, Success Rate (%), Successful Calls, Failed Calls.
2. **Success Rate Progress Indicator:** Visual progress ring & percentage.
3. **Failure Analysis:** Category breakdown for failed calls to identify optimization areas.
4. **Recent Call Log:** Live updating feed showing channel (Browser vs SIP), duration, outcome badge, and timestamp.
5. **Auto-refresh:** Polling every 15 seconds to show live session data.

---

## How to Test

### 1. Start Backend & API Server
```powershell
cd E:\Murf\murf-livekit-starter\backend
uv run python src/agent.py dev
```

### 2. Start Frontend
```powershell
cd E:\Murf\murf-livekit-starter\frontend
pnpm dev
```

### 3. Open the Analytics Dashboard
Navigate to `http://localhost:3000/dashboard` in your browser.

### 4. Make Calls & Verify Metrics
- Place an order or trigger an escalation via the browser assistant.
- End the call and check the dashboard to verify duration, channel, and success status!

---

## Day 8 Checklist

- [x] Defined clear call outcome taxonomy (Success vs Failed)
- [x] Defined failure taxonomy (`user_hangup`, `incomplete_task`, `tool_error`, `no_response`)
- [x] Implemented `call_analytics` SQLite table with zero PII
- [x] Created Analytics HTTP API routes in `backend/src/analytics_api.py`
- [x] Wired agent session lifecycle hooks in `backend/src/agent.py`
- [x] Created Next.js Analytics Dashboard at `/dashboard`
- [x] Added top navigation header bar linking Store Front, Escalations, and Dashboard
- [x] Code committed and pushed to both remote repositories

---

*Part of the 10 Days of Voice Agents challenge — powered by LiveKit & Murf Falcon TTS.*
