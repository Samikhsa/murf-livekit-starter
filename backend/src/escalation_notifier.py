"""
escalation_notifier.py -- Discord webhook notifier for ShopMitra (Day 7)

Sends a rich Discord embed when a human-help escalation ticket is created.
Never sends raw conversation transcripts or PII (PII is already scrubbed
before this module is called).

Public API
----------
post_escalation_to_discord(ticket: dict) -> bool
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)

logger = logging.getLogger("agent.escalation_notifier")

# ---------------------------------------------------------------------------
# Discord embed colour map by urgency
# ---------------------------------------------------------------------------
_URGENCY_COLOURS = {
    "emergency": 0x2C2F33,   # near-black
    "high":      0xE74C3C,   # red
    "medium":    0xE67E22,   # orange
    "low":       0x3498DB,   # blue
}

_URGENCY_EMOJI = {
    "emergency": "??",
    "high":      "??",
    "medium":    "??",
    "low":       "??",
}

_REASON_LABEL = {
    "payment_dispute": "?? Payment / Refund Dispute",
    "order_dispute":   "?? Order / Delivery Dispute",
}


async def post_escalation_to_discord(ticket: dict) -> bool:
    """
    Post an escalation ticket to the configured Discord webhook.

    Args:
        ticket: The full escalation dict returned by database.create_escalation().

    Returns:
        True if the webhook responded with 2xx, False otherwise.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set -- skipping Discord notification.")
        return False

    try:
        import aiohttp
    except ImportError:
        logger.error("aiohttp is not installed -- cannot post to Discord.")
        return False

    urgency = ticket.get("urgency", "medium").lower()
    reason_type = ticket.get("reason_type", "")
    colour = _URGENCY_COLOURS.get(urgency, 0x95A5A6)
    emoji = _URGENCY_EMOJI.get(urgency, "?")
    reason_label = _REASON_LABEL.get(reason_type, reason_type.replace("_", " ").title())

    follow_up = ticket.get("follow_up_method", "call").title()
    language = ticket.get("language", "en").upper()

    embed = {
        "title": f"{emoji} New Escalation -- {ticket.get('ref_id', 'N/A')}",
        "description": ticket.get("summary", "No summary provided."),
        "color": colour,
        "fields": [
            {"name": "?? Reason",         "value": reason_label,                             "inline": True},
            {"name": "? Urgency",         "value": urgency.upper(),                          "inline": True},
            {"name": "?? Caller Name",     "value": ticket.get("caller_name", "Unknown"),     "inline": True},
            {"name": "??? Language",        "value": language,                                 "inline": True},
            {"name": "?? Follow-up via",   "value": follow_up,                                "inline": True},
            {"name": "?? Status",          "value": ticket.get("status", "open").upper(),     "inline": True},
            {"name": "?? Agent Checked",   "value": ticket.get("agent_checked") or "N/A",     "inline": False},
        ],
        "footer": {"text": "ABC ShopMitra - Human Escalation System - Day 7"},
        "timestamp": ticket.get("created_at", ""),
    }

    payload = {
        "username": "ShopMitra Escalation Bot",
        "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png",
        "embeds": [embed],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url, json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status in (200, 204):
                    logger.info(
                        "Escalation %s posted to Discord (HTTP %d).",
                        ticket.get("ref_id"), resp.status
                    )
                    return True
                else:
                    body = await resp.text()
                    logger.error(
                        "Discord webhook returned HTTP %d for escalation %s: %s",
                        resp.status, ticket.get("ref_id"), body[:200],
                    )
                    return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Discord webhook failed for escalation %s: %s", ticket.get("ref_id"), exc)
        return False


def post_escalation_sync(ticket: dict) -> bool:
    """Fire-and-forget wrapper safe to call from async agent tools."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(post_escalation_to_discord(ticket))
            return True
        return loop.run_until_complete(post_escalation_to_discord(ticket))
    except RuntimeError:
        return asyncio.run(post_escalation_to_discord(ticket))
