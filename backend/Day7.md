# Day 7 — Know When to Ask for Human Help

## What Was Built

ShopMitra now knows when to stop and ask a human for help.

### Two Escalation Triggers

| Situation | Reason Type | Urgency |
|-----------|-------------|---------|
| Payment / Refund Dispute | `payment_dispute` | HIGH 🔴 |
| Order / Delivery Dispute | `order_dispute` | MEDIUM 🟠 |

### New Tools

| Tool | Purpose |
|------|---------|
| `create_escalation` | Creates a ticket after caller consent. Deduplicates, scrubs PII, posts to Discord. |
| `check_escalation_status` | Lets a caller check the status of an existing ticket by ref ID. |

### Flow

1. Agent detects trigger (payment or order dispute)
2. Agent empathetically acknowledges and tells caller what will be shared
3. Agent asks: "May I create a support request?"
4. If YES → `create_escalation` → Discord webhook fires → caller gets ref ID
5. If NO → agent offers store phone number (+91-98765-43210)

### Privacy

- Summary is scrubbed for phone numbers, OTPs, PINs, tracking codes before saving
- Conversation transcript is never sent
- Payment credentials, CVV, account numbers are never collected

### Reference IDs

Format: `ESC-YYYYMMDD-NNNN` (e.g. `ESC-20260812-0001`)
Sequential within each day, readable aloud.

### Deduplication

If the same user has an open ticket for the same reason type, the agent
tells them their existing ref ID instead of creating a duplicate.

### Dashboard

Visit: http://localhost:3000/escalations

Shows all tickets with:
- Colour-coded urgency (red=high, orange=medium, blue=low)
- Animated status pills (open, in progress, resolved)
- One-click status update buttons
- Auto-refreshes every 30 seconds

### Discord Notifications

Each new ticket fires a Discord embed to DISCORD_WEBHOOK_URL.
Set this in `backend/.env.local`.

### Escalation API

Lightweight aiohttp server runs on port 8765 alongside the agent:
- GET  /api/escalations            → list all tickets
- GET  /api/escalations?status=open → filter by status
- GET  /api/escalations/<ref_id>   → single ticket
- POST /api/escalations/<ref_id>/resolve    → mark resolved
- POST /api/escalations/<ref_id>/inprogress → mark in_progress

### Files Changed / Created

| File | Change |
|------|--------|
| `src/agent.py` | Added 2 tools, updated system prompt |
| `src/database.py` | Added escalations table + 5 DB functions |
| `src/escalation_notifier.py` | NEW — Discord webhook poster |
| `src/escalation_api.py` | NEW — aiohttp HTTP API server |
| `frontend/app/escalations/page.tsx` | NEW — premium dashboard |
| `frontend/app/api/escalations/route.ts` | NEW — Next.js proxy |
| `backend/.env.local` | Added DISCORD_WEBHOOK_URL + port |
| `pyproject.toml` | Added aiohttp dependency |
