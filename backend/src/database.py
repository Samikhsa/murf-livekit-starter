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
    """Create the users and outbound_calls tables if they do not exist."""
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
    conn.commit()
    logger.info("Database schema ready for inbound and outbound calls.")



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

