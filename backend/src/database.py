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
    """Create the users table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id             TEXT PRIMARY KEY,
            name                TEXT NOT NULL,
            language_preference TEXT DEFAULT 'en',
            facts               TEXT DEFAULT '{}',
            last_interaction    TEXT NOT NULL
        )
        """
    )
    conn.commit()
    logger.info("Database schema ready.")


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
