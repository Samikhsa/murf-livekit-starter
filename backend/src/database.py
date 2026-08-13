"""
database.py — Persistent caller memory for ShopMitra (Day 4)

Uses the Python stdlib sqlite3 module — no extra dependencies needed.
The database file is stored at backend/data/shopmitra.db and persists
across agent restarts.

Public API
----------
get_user(user_id: str) -> dict | None
upsert_user(user_id, name, *, language_preference, facts) -> None
delete_user(user_id: str) -> bool          # "forget me" (advanced)

# Day 7 — Human Escalation
create_escalation(...) -> dict              # create a new escalation ticket
get_escalation(ref_id: str) -> dict | None
list_escalations(status, limit) -> list[dict]
update_escalation_status(ref_id, status) -> dict | None
find_open_escalation(user_id, reason_type) -> dict | None

# Day 8 — Call Analytics
record_call_start(call_id, room_name, channel) -> dict
record_call_end(call_id, outcome, failure_type, duration_seconds) -> dict | None
get_call_stats() -> dict
list_recent_calls(limit) -> list[dict]
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("agent.database")

# ---------------------------------------------------------------------------
# Location of the database file
# ---------------------------------------------------------------------------
_DB_DIR = Path(__file__).resolve().parents[1] / "data"
_DB_PATH = _DB_DIR / "shopmitra.db"

# Module-level connection (lazily created) + lock for thread safety
_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return (and lazily create) the shared SQLite connection."""
    global _conn
    if _conn is None:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(
            str(_DB_PATH),
            check_same_thread=False,   # we guard with _lock
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        _conn.row_factory = sqlite3.Row
        _create_tables(_conn)
        logger.info("SQLite database opened at %s", _DB_PATH)
    return _conn


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create the users, outbound_calls, escalations, and call_analytics tables if they do not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id             TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            language_preference TEXT DEFAULT 'en',
            facts               TEXT DEFAULT '{}',
            last_interaction    TEXT NOT NULL,
            opted_out           INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outbound_calls (
            call_id         TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            phone_number    TEXT NOT NULL,
            customer_name   TEXT NOT NULL,
            restock_item    TEXT NOT NULL,
            status          TEXT NOT NULL, -- CALLING, CONNECTED, NO_ANSWER, BUSY, VOICEMAIL, IMMEDIATE_HANGUP
            outcome_notes   TEXT DEFAULT '',
            attempt_count   INTEGER DEFAULT 1,
            next_retry_at   TEXT DEFAULT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
        """
    )
    # Day 7 — Human Escalation tickets
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS escalations (
            ref_id           TEXT PRIMARY KEY,   -- e.g. ESC-20260812-0001
            user_id          TEXT NOT NULL,
            caller_name      TEXT NOT NULL,
            reason_type      TEXT NOT NULL,      -- payment_dispute | order_dispute
            summary          TEXT NOT NULL,      -- short PII-scrubbed human-readable summary
            urgency          TEXT NOT NULL,      -- low | medium | high | emergency
            language         TEXT DEFAULT 'en',
            follow_up_method TEXT DEFAULT 'call', -- call | whatsapp | sms
            agent_checked    TEXT DEFAULT '',    -- what the agent already verified
            status           TEXT DEFAULT 'open', -- open | in_progress | resolved
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL
        )
        """
    )
    # Day 8 — Call Analytics (no PII stored: no names, no phone numbers, no transcripts)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS call_analytics (
            call_id          TEXT PRIMARY KEY,
            room_name        TEXT NOT NULL,
            channel          TEXT NOT NULL DEFAULT 'browser',  -- browser | sip
            outcome          TEXT NOT NULL DEFAULT 'pending',  -- pending | success | failed
            failure_type     TEXT DEFAULT NULL,                -- user_hangup | incomplete_task | tool_error | no_response
            duration_seconds INTEGER DEFAULT 0,
            started_at       TEXT NOT NULL,
            ended_at         TEXT DEFAULT NULL
        )
        """
    )
    conn.commit()
    logger.info("Database schema ready for inbound calls, outbound calls, escalations, and call analytics.")



def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite3.Row to a plain dict, parsing the facts JSON blob."""
    if row is None:
        return None
    d = dict(row)
    try:
        d["facts"] = json.loads(d.get("facts") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["facts"] = {}
    return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_user(user_id: str) -> dict | None:
    """
    Look up a caller by their user_id.

    Returns a dict with keys:
        user_id, name, language_preference, facts (dict), last_interaction
    Returns None if the user is not found.
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = cur.fetchone()
    result = _row_to_dict(row)
    if result:
        logger.info("Found existing user: %s (%s)", result["name"], user_id)
    else:
        logger.info("No record found for user_id=%s", user_id)
    return result


def upsert_user(
    user_id: str,
    name: str,
    *,
    language_preference: str = "en",
    facts: dict | None = None,
) -> dict:
    """
    Insert or update a caller's profile.

    If a record already exists for user_id, only the supplied fields are
    merged into the existing ones (existing facts are not wiped).

    Returns the full updated record.
    """
    if facts is None:
        facts = {}

    now = datetime.now(timezone.utc).isoformat()

    with _lock:
        conn = _get_conn()

        # Fetch existing record so we can merge facts rather than replace them
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        existing = _row_to_dict(cur.fetchone())

        if existing:
            merged_facts = {**existing["facts"], **facts}
            conn.execute(
                """
                UPDATE users
                SET name = ?,
                    language_preference = ?,
                    facts = ?,
                    last_interaction = ?
                WHERE user_id = ?
                """,
                (
                    name,
                    language_preference,
                    json.dumps(merged_facts, ensure_ascii=False),
                    now,
                    user_id,
                ),
            )
            logger.info("Updated record for user %s (%s)", name, user_id)
        else:
            merged_facts = facts
            conn.execute(
                """
                INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    language_preference,
                    json.dumps(merged_facts, ensure_ascii=False),
                    now,
                ),
            )
            logger.info("Created new record for user %s (%s)", name, user_id)

        conn.commit()

    return get_user(user_id)  # type: ignore[return-value]


def delete_user(user_id: str) -> bool:
    """
    Delete a caller's record ("forget me" feature — advanced Day 4 goal).

    Returns True if a row was deleted, False if no record existed.
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        deleted = cur.rowcount > 0

    if deleted:
        logger.info("Deleted record for user_id=%s", user_id)
    else:
        logger.info("delete_user: no record found for user_id=%s", user_id)
    return deleted


# ---------------------------------------------------------------------------
# Outbound Calls & Opt-Out Management (Day 6)
# ---------------------------------------------------------------------------

def set_user_opt_out(user_id: str, opted_out: bool = True) -> bool:
    """Set opt-out preference for restock calls."""
    user = get_user(user_id)
    if not user:
        upsert_user(user_id, name="Valued Customer", facts={})
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "UPDATE users SET opted_out = ? WHERE user_id = ?",
            (1 if opted_out else 0, user_id),
        )
        conn.commit()
        updated = cur.rowcount > 0
    logger.info("set_user_opt_out: user_id=%s opted_out=%s", user_id, opted_out)
    return updated



def is_user_opted_out(user_id: str) -> bool:
    """Check if user has opted out of restock calls."""
    user = get_user(user_id)
    if user and user.get("opted_out"):
        return True
    return False


def record_outbound_call(
    call_id: str,
    user_id: str,
    phone_number: str,
    customer_name: str,
    restock_item: str,
    status: str = "CALLING",
    attempt_count: int = 1,
) -> dict:
    """Record a new outbound call attempt."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO outbound_calls
            (call_id, user_id, phone_number, customer_name, restock_item, status, attempt_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (call_id, user_id, phone_number, customer_name, restock_item, status, attempt_count, now, now),
        )
        conn.commit()
    logger.info("Recorded outbound call call_id=%s status=%s to %s", call_id, status, phone_number)
    return get_outbound_call(call_id)  # type: ignore[return-value]


def update_outbound_call_outcome(
    call_id: str,
    status: str,
    outcome_notes: str = "",
    next_retry_at: str | None = None,
) -> dict | None:
    """Update call outcome status, notes, and retry time."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            UPDATE outbound_calls
            SET status = ?, outcome_notes = ?, next_retry_at = ?, updated_at = ?
            WHERE call_id = ?
            """,
            (status, outcome_notes, next_retry_at, now, call_id),
        )
        conn.commit()
    logger.info("Updated call outcome call_id=%s status=%s notes=%s retry=%s", call_id, status, outcome_notes, next_retry_at)
    return get_outbound_call(call_id)


def get_outbound_call(call_id: str) -> dict | None:
    """Fetch an outbound call record by call_id."""
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT * FROM outbound_calls WHERE call_id = ?", (call_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_outbound_calls(limit: int = 20) -> list[dict]:
    """Fetch recent outbound calls."""
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT * FROM outbound_calls ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Day 7 — Human Escalation API
# ---------------------------------------------------------------------------

import re as _re
from datetime import date as _date

# Patterns to scrub from summaries before saving / sending
_PII_PATTERNS = [
    (_re.compile(r'\b\d{10,13}\b'), '<phone>'),                             # phone numbers
    (_re.compile(r'(?i)\bOTP\s*[:\-]?\s*\d+\b'), '<otp-redacted>'),        # OTP with digits
    (_re.compile(r'\b\d{4,6}\b(?=\s*(otp|pin|cvv))', _re.I), '<redacted>'), # digits before OTP/PIN
    (_re.compile(r'\b[A-Z]{2}\d{10,14}\b'), '<tracking-id>'),               # tracking/order codes
]


def _scrub_pii(text: str) -> str:
    """Remove common PII patterns from a text string before storing / sending."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text.strip()


def _generate_ref_id() -> str:
    """
    Generate a sequential, date-stamped reference ID like ESC-20260812-0001.
    Must be called while NOT holding _lock (it acquires it internally).
    """
    today = _date.today().strftime("%Y%m%d")
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            "SELECT COUNT(*) FROM escalations WHERE ref_id LIKE ?",
            (f"ESC-{today}-%",)
        )
        count = cur.fetchone()[0]
    seq = count + 1
    return f"ESC-{today}-{seq:04d}"


def create_escalation(
    user_id: str,
    caller_name: str,
    reason_type: str,
    summary: str,
    urgency: str = "medium",
    language: str = "en",
    follow_up_method: str = "call",
    agent_checked: str = "",
) -> dict:
    """
    Create a new human-help escalation ticket.

    Automatically scrubs PII from summary and agent_checked before saving.
    Returns the full ticket dict including the generated ref_id.
    """
    ref_id = _generate_ref_id()
    now = datetime.now(timezone.utc).isoformat()
    clean_summary = _scrub_pii(summary)
    clean_agent_checked = _scrub_pii(agent_checked)

    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO escalations
            (ref_id, user_id, caller_name, reason_type, summary, urgency,
             language, follow_up_method, agent_checked, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (
                ref_id, user_id, caller_name, reason_type, clean_summary, urgency,
                language, follow_up_method, clean_agent_checked, now, now,
            ),
        )
        conn.commit()
    logger.info(
        "Escalation created: ref_id=%s user_id=%s reason=%s urgency=%s",
        ref_id, user_id, reason_type, urgency,
    )
    return get_escalation(ref_id)  # type: ignore[return-value]


def get_escalation(ref_id: str) -> dict | None:
    """Fetch a single escalation ticket by ref_id."""
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT * FROM escalations WHERE ref_id = ?", (ref_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def list_escalations(status: str | None = None, limit: int = 50) -> list[dict]:
    """Fetch escalation tickets, optionally filtered by status, newest first."""
    with _lock:
        conn = _get_conn()
        if status:
            cur = conn.execute(
                "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM escalations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_escalation_status(ref_id: str, status: str) -> dict | None:
    """Update the status of an escalation ticket (open / in_progress / resolved)."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            "UPDATE escalations SET status = ?, updated_at = ? WHERE ref_id = ?",
            (status, now, ref_id),
        )
        conn.commit()
    logger.info("Escalation status updated: ref_id=%s status=%s", ref_id, status)
    return get_escalation(ref_id)


def find_open_escalation(user_id: str, reason_type: str) -> dict | None:
    """
    Find an already-open escalation for the same user and reason type.
    Used to prevent duplicate tickets from the same caller.
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            """
            SELECT * FROM escalations
            WHERE user_id = ? AND reason_type = ? AND status = 'open'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, reason_type),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Day 8 — Call Analytics (no PII stored)
# ---------------------------------------------------------------------------

def record_call_start(
    call_id: str,
    room_name: str,
    channel: str = "browser",
) -> dict:
    """
    Record the start of a new call session in call_analytics.

    Args:
        call_id:   Unique identifier for this call (e.g. room name or UUID).
        room_name: LiveKit room name.
        channel:   'browser' or 'sip'.
    Returns the new call record.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO call_analytics
            (call_id, room_name, channel, outcome, started_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (call_id, room_name, channel, now),
        )
        conn.commit()
    logger.info("Call started: call_id=%s room=%s channel=%s", call_id, room_name, channel)
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT * FROM call_analytics WHERE call_id = ?", (call_id,))
        row = cur.fetchone()
    return dict(row) if row else {"call_id": call_id, "room_name": room_name, "channel": channel}


def record_call_end(
    call_id: str,
    outcome: str,
    failure_type: str | None = None,
    duration_seconds: int = 0,
) -> dict | None:
    """
    Update the outcome of a call when its session ends.

    Args:
        call_id:          The same call_id used in record_call_start.
        outcome:          'success' | 'failed'
        failure_type:     Optional reason for failure:
                          'user_hangup' | 'incomplete_task' | 'tool_error' | 'no_response'
        duration_seconds: Call duration in whole seconds.
    Returns the updated call record, or None if call_id not found.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            UPDATE call_analytics
            SET outcome = ?, failure_type = ?, duration_seconds = ?, ended_at = ?
            WHERE call_id = ?
            """,
            (outcome, failure_type, duration_seconds, now, call_id),
        )
        conn.commit()
    logger.info(
        "Call ended: call_id=%s outcome=%s failure_type=%s duration=%ds",
        call_id, outcome, failure_type, duration_seconds,
    )
    with _lock:
        conn = _get_conn()
        cur = conn.execute("SELECT * FROM call_analytics WHERE call_id = ?", (call_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_call_stats() -> dict:
    """
    Return aggregate call statistics for the dashboard.

    Returns a dict with keys:
        total, successful, failed, pending, success_rate (0.0–100.0)
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            """
            SELECT
                COUNT(*)                                        AS total,
                SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS successful,
                SUM(CASE WHEN outcome = 'failed'  THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) AS pending
            FROM call_analytics
            """
        )
        row = cur.fetchone()

    total     = row["total"]      or 0
    successful = row["successful"] or 0
    failed    = row["failed"]     or 0
    pending   = row["pending"]    or 0

    completed = successful + failed
    success_rate = round((successful / completed * 100), 1) if completed > 0 else 0.0

    return {
        "total":        total,
        "successful":   successful,
        "failed":       failed,
        "pending":      pending,
        "success_rate": success_rate,
    }


def list_recent_calls(limit: int = 20) -> list[dict]:
    """
    Return the most recent call records for the dashboard.

    Privacy: only call_id, room_name, channel, outcome, failure_type, duration,
    started_at, ended_at are returned — no caller names, phone numbers, or transcripts.
    """
    with _lock:
        conn = _get_conn()
        cur = conn.execute(
            """
            SELECT call_id, room_name, channel, outcome, failure_type,
                   duration_seconds, started_at, ended_at
            FROM call_analytics
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
