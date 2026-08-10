# Db.md — Day 4: Giving Your Voice Agent a Persistent Memory

A complete reference for **how and why** the ShopMitra agent stores caller data, with enough detail that you can reproduce this pattern in any future project.

---

## Why SQLite?

| Option | Why we chose / didn't choose it |
|--------|----------------------------------|
| **SQLite** ✅ | Zero install — it's part of Python's stdlib. One file on disk. Perfect for a single-server demo or prototype. |
| Postgres | Production-grade, but requires a running server and `asyncpg`/`psycopg2`. Overkill for Day 4. |
| MongoDB | Schemaless JSON storage is nice, but adds the `motor` or `pymongo` dependency. |

**Rule of thumb**: Start with SQLite. Migrate to Postgres when you need concurrent writes from multiple servers.

---

## Database Location

```
backend/
└── data/
    └── shopmitra.db   ← created automatically on first run
```

The `data/` folder is created by `database.py` if it doesn't exist. The `.db` file **persists across agent restarts** — that is the whole point.

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id             TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    language_preference TEXT DEFAULT 'en',
    facts               TEXT DEFAULT '{}',   -- JSON blob
    last_interaction    TEXT NOT NULL         -- ISO 8601 UTC timestamp
);
```

### Facts blob (Local Commerce track)

```json
{
  "past_orders":              "rice 5kg, dal 2kg, cooking oil",
  "usual_quantities":         "5 kg rice weekly, 2 L milk daily",
  "preferred_delivery_slot":  "morning"
}
```

The `facts` column stores a JSON string. `database.py` parses it back to a Python dict on every read, so callers of `get_user()` always get a real dict — never a raw string.

---

## Public API — `backend/src/database.py`

### `get_user(user_id: str) -> dict | None`

Reads a single row. Returns `None` for unknown callers.

```python
from src import database

record = database.get_user("room-abc-123")
# Returns:
# {
#   "user_id": "room-abc-123",
#   "name": "Ramesh",
#   "language_preference": "hi",
#   "facts": {
#       "past_orders": "rice, dal",
#       "usual_quantities": "5 kg",
#       "preferred_delivery_slot": "morning"
#   },
#   "last_interaction": "2026-08-09T04:12:00+00:00"
# }
```

### `upsert_user(user_id, name, *, language_preference, facts) -> dict`

Insert **or** update. Facts are **merged** (not replaced) so you never accidentally wipe a field the agent didn't touch this session.

```python
database.upsert_user(
    "room-abc-123",
    "Ramesh",
    language_preference="hi",
    facts={
        "past_orders": "rice 5kg, dal 2kg",
        "usual_quantities": "5 kg rice",
        "preferred_delivery_slot": "morning",
    },
)
```

### `delete_user(user_id: str) -> bool`

Wipes the record entirely. Returns `True` if a row was deleted. Used by the `forget_caller` tool.

---

## How the Agent Uses the Database

The agent has **three function tools** (defined in `Assistant` in `agent.py`):

```
lookup_caller(user_id)
    └─ calls database.get_user()
    └─ returns profile or "new_caller" status
    └─ agent greets returning callers by name

save_caller_info(user_id, name, language_preference, past_orders, usual_quantities, preferred_delivery_slot)
    └─ ONLY called after explicit verbal consent
    └─ calls database.upsert_user()

forget_caller(user_id)
    └─ called when user asks to be forgotten
    └─ calls database.delete_user()
```

### Call flow — new caller

```
Session starts
  └─ agent receives user_id in initial instructions
  └─ calls lookup_caller("room-xyz")
        └─ returns {status: "new_caller"}
  └─ agent delivers default greeting
  ...conversation...
  └─ agent asks: "Is it okay if I remember your preferences?"
  └─ caller says YES
  └─ agent calls save_caller_info(...)
  └─ agent: "Great, I'll remember that for next time!"
```

### Call flow — returning caller

```
Session starts
  └─ agent calls lookup_caller("room-xyz")
        └─ returns {status: "returning_caller", name: "Ramesh", facts: {...}}
  └─ agent: "Welcome back, Ramesh! Last time you asked about rice in bulk —
             shall I check if we have stock today?"
```

---

## How `user_id` Is Derived

```python
# In agent.py → _derive_user_id()
# Priority 1: LiveKit participant identity (set by your auth layer)
for p in ctx.room.remote_participants.values():
    if p.identity:
        return p.identity

# Priority 2: Room name (stable for the Day 4 demo)
return ctx.room.name or "unknown_caller"
```

**For production**: Pass a real authenticated user ID as the participant identity when generating the LiveKit token in your frontend. The agent will pick it up automatically.

---

## Consent Rule (Hard Requirement)

The system prompt contains this rule:

> **BEFORE saving ANYTHING, explicitly ask the caller for permission.  
> If they say NO or are hesitant — do NOT call `save_caller_info`.**

This is enforced at the LLM instruction level. The tool itself has no consent check — the LLM is responsible for only calling it after consent. This mirrors how real production systems work: the AI model is your last line of defense, not the database.

For **Financial Services** or **Health Access** tracks, you would add a hard server-side gate (e.g., store a `consent_given` flag and reject writes without it).

---

## Inspecting the Database Manually

```bash
# From the backend/ folder
sqlite3 data/shopmitra.db

# Useful queries
.headers on
.mode column
SELECT user_id, name, language_preference, last_interaction FROM users;
SELECT facts FROM users WHERE name = 'Ramesh';
```

---

## Migrating to Postgres (when you're ready)

1. Install `asyncpg`: `uv add asyncpg`
2. Replace `sqlite3` connection logic in `database.py` with an `asyncpg` pool
3. Change the `CREATE TABLE` DDL: `TEXT PRIMARY KEY` → `VARCHAR(255) PRIMARY KEY`, `TEXT` → `JSONB` for the facts column
4. Replace `?` placeholders with `$1, $2, ...`
5. Set `DATABASE_URL` in `.env.local`

The public API (`get_user`, `upsert_user`, `delete_user`) stays identical — nothing in `agent.py` needs to change.

---

## Migrating to MongoDB (when you're ready)

1. Install `motor`: `uv add motor`
2. Replace `database.py` internals with `motor.AsyncIOMotorClient`
3. Each user record maps directly to a MongoDB document — the `facts` dict embeds naturally
4. Set `MONGODB_URI` in `.env.local`

Again, the public API stays the same.

---

## Day 4 Checklist

- [x] SQLite DB file persists across restarts (`backend/data/shopmitra.db`)
- [x] Agent reads caller info via `lookup_caller` tool (not the prompt)
- [x] Returning callers are greeted by name with personalised context
- [x] Agent always asks for consent before calling `save_caller_info`
- [x] "Forget me" tool (`forget_caller`) wipes the record completely
- [x] Language detection — Hindi replied in Devanagari, never romanized

---

*Part of the 10 Days of Voice Agents challenge — powered by Murf Falcon TTS.*
