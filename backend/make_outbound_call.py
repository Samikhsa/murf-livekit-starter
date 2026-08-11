#!/usr/bin/env python3
"""
make_outbound_call.py — Day 6 Outbound Restock Call Trigger

Triggers an outbound restock nudge call from ShopMitra to a customer.

Usage:
    # With full SIP (after setting LIVEKIT_SIP_TRUNK_ID in .env.local):
    uv run python make_outbound_call.py --phone +919876543210 --name "Ramesh Kumar" --item "Basmati Rice 5kg & Wheat Flour 10kg"

    # Read phone number from .env.local (TO_PHONE_NUMBER):
    uv run python make_outbound_call.py

    # Simulate specific outcomes (for testing outcome handling):
    uv run python make_outbound_call.py --phone +919876543210 --outcome NO_ANSWER
    uv run python make_outbound_call.py --phone +919876543210 --outcome BUSY
    uv run python make_outbound_call.py --phone +919876543210 --outcome VOICEMAIL

The script prints:
    - The call_id and dispatch status
    - The mandatory 3-part opening the agent will say
    - The outcome record written to the SQLite database
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow running from the repo root or the backend/ folder
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR / "src"))

from dotenv import load_dotenv

load_dotenv(_BACKEND_DIR / ".env.local", override=False)

from outbound_caller import initiate_outbound_call  # noqa: E402

# ---------------------------------------------------------------------------
# Colours for terminal output
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _banner():
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  ShopMitra -- Outbound Restock Call Trigger (Day 6){RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")


def _print_result(result: dict):
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}CALL DISPATCH RESULT{RESET}")
    print(f"{'=' * 60}")

    status = result.get("outcome", {}).get("status", "unknown")
    dispatched = result.get("livekit_dispatched", False)
    mode = result.get("dispatch_mode", "none")

    colour = GREEN if dispatched else YELLOW

    print(f"  Call ID      : {result.get('call_id', 'N/A')}")
    print(f"  Customer     : {result.get('customer_name', 'N/A')}")
    print(f"  Phone        : {result.get('phone_number', 'N/A')}")
    print(f"  Restock Item : {result.get('restock_item', 'N/A')}")
    print(f"  Dispatched   : {colour}{dispatched}{RESET}")
    print(f"  Mode         : {colour}{mode}{RESET}")
    print(f"  Outcome      : {status}")

    notes = result.get("outcome", {}).get("outcome_notes", "")
    if notes:
        print(f"  Notes        : {notes}")

    retry_at = result.get("outcome", {}).get("next_retry_at")
    if retry_at:
        print(f"  {YELLOW}Next Retry   : {retry_at}{RESET}")

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}MANDATORY 3-PART OPENING (what the agent will say){RESET}")
    print(f"{'=' * 60}")
    print(f"{GREEN}{result.get('mandatory_opening', '')}{RESET}")
    print(f"{'=' * 60}\n")

    if mode == "sip_trunk":
        print(f"{GREEN}[OK] Live SIP call placed -- your phone should ring shortly!{RESET}")
    elif mode == "room_only":
        print(
            f"{YELLOW}[WARN] Room created (simulation mode). "
            f"No SIP trunk configured -- phone will NOT ring.{RESET}"
        )
        print(
            f"   To enable live calls: add LIVEKIT_SIP_TRUNK_ID to backend/.env.local"
        )
        print(
            f"   See backend/Day6.md for full Twilio setup instructions.\n"
        )
    elif result.get("outcome", {}).get("status") == "SKIPPED_OPTED_OUT":
        print(f"{RED}[SKIP] Call skipped -- customer has opted out of restock calls.{RESET}\n")


async def _run(args):
    phone = args.phone or os.getenv("TO_PHONE_NUMBER", "")
    if not phone or phone in ("+91XXXXXXXXXX", "+1XXXXXXXXXX"):
        print(
            f"{RED}ERROR: No valid phone number provided.{RESET}\n"
            f"  Pass --phone +919876543210  OR  set TO_PHONE_NUMBER in backend/.env.local"
        )
        sys.exit(1)

    result = await initiate_outbound_call(
        phone_number=phone,
        customer_name=args.name,
        restock_item=args.item,
        user_id=args.user_id or None,
        simulate_outcome=args.outcome if args.outcome != "CONNECTED" else None,
    )
    _print_result(result)


def main():
    _banner()
    parser = argparse.ArgumentParser(
        description="Trigger an outbound restock call from ShopMitra",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--phone", "--to",
        dest="phone",
        default="",
        help="Phone number or Linphone username to call (e.g. +919876543210 or your-username). "
             "Falls back to TO_PHONE_NUMBER in .env.local.",
    )
    parser.add_argument(
        "--name",
        default="Ramesh Kumar",
        help="Customer name (default: Ramesh Kumar)",
    )
    parser.add_argument(
        "--item",
        default="Basmati Rice 5kg & Wheat Flour 10kg",
        help="Restock item description",
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        default="",
        help="Optional stable user ID. Auto-generated from phone number if omitted.",
    )
    parser.add_argument(
        "--outcome",
        choices=["CONNECTED", "NO_ANSWER", "BUSY", "VOICEMAIL", "IMMEDIATE_HANGUP", "OPTED_OUT"],
        default="CONNECTED",
        help="Simulate a specific call outcome (for testing retry logic). Default: CONNECTED.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
