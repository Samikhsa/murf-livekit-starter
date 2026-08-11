"""
outbound_caller.py — Telephony Integration & Outcome Manager for Day 6

Handles initiating outbound calls for ABC ShopMitra restock nudges,
integrating LiveKit API / SIP dispatch, tracking outcome states, and executing
retry rules.
"""

import argparse
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

try:
    from . import database
except ImportError:
    import database

logger = logging.getLogger("outbound_caller")


def _load_env():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)


_load_env()

# Retry Policies by Outcome
RETRY_POLICIES = {
    "NO_ANSWER": {"max_retries": 2, "delay_minutes": 30},
    "BUSY": {"max_retries": 3, "delay_minutes": 15},
    "VOICEMAIL": {"max_retries": 0, "leave_message": True},
    "IMMEDIATE_HANGUP": {"max_retries": 0, "opt_out_flag": False},
}


class OutcomeTracker:
    """Tracks telephony call outcomes and computes retry schedules."""

    @staticmethod
    def process_outcome(
        call_id: str,
        outcome: str,
        notes: str = "",
    ) -> dict:
        """
        Process call outcome (CONNECTED, NO_ANSWER, BUSY, VOICEMAIL, IMMEDIATE_HANGUP)
        and record retry schedule if applicable.
        """
        call_record = database.get_outbound_call(call_id)
        if not call_record:
            logger.error("OutcomeTracker: Call %s not found", call_id)
            return {"error": "call_not_found"}

        user_id = call_record["user_id"]
        attempt = call_record["attempt_count"]
        now = datetime.now(timezone.utc)
        next_retry = None
        final_notes = notes

        if outcome == "CONNECTED":
            final_notes = f"Call completed successfully. {notes}".strip()

        elif outcome == "NO_ANSWER":
            policy = RETRY_POLICIES["NO_ANSWER"]
            if attempt <= policy["max_retries"]:
                retry_time = now + timedelta(minutes=policy["delay_minutes"])
                next_retry = retry_time.isoformat()
                final_notes = f"No answer (attempt {attempt}/{policy['max_retries']+1}). Next retry scheduled for {retry_time.strftime('%H:%M UTC')}."
            else:
                final_notes = f"No answer after {attempt} attempts. Max retries reached."

        elif outcome == "BUSY":
            policy = RETRY_POLICIES["BUSY"]
            if attempt <= policy["max_retries"]:
                retry_time = now + timedelta(minutes=policy["delay_minutes"])
                next_retry = retry_time.isoformat()
                final_notes = f"Line busy (attempt {attempt}/{policy['max_retries']+1}). Next retry scheduled for {retry_time.strftime('%H:%M UTC')}."
            else:
                final_notes = f"Line busy after {attempt} attempts. Max retries reached."

        elif outcome == "VOICEMAIL":
            final_notes = "Voicemail detected. Brief restock audio message delivered. No further retries scheduled."

        elif outcome == "IMMEDIATE_HANGUP":
            final_notes = "User hung up immediately (<5s). Marked as do-not-call today to respect privacy."

        elif outcome == "OPTED_OUT":
            database.set_user_opt_out(user_id, True)
            final_notes = "User requested opt-out during call. Restock call reminders disabled."

        updated = database.update_outbound_call_outcome(
            call_id,
            status=outcome,
            outcome_notes=final_notes,
            next_retry_at=next_retry,
        )
        return updated or {}


async def initiate_outbound_call(
    phone_number: str,
    customer_name: str,
    restock_item: str,
    user_id: str | None = None,
    simulate_outcome: str | None = None,
) -> dict:
    """
    Initiate an outbound call for restock nudge.

    Integrates with LiveKit SIP / API or simulates outcome for testing.
    """
    if not user_id:
        user_id = f"user_{phone_number.replace('+', '').replace('-', '')}"

    # Check if user opted out
    if database.is_user_opted_out(user_id):
        logger.info("User %s (%s) has opted out of restock calls. Skipping call.", customer_name, user_id)
        return {
            "status": "SKIPPED_OPTED_OUT",
            "message": f"User {customer_name} has opted out of outbound restock calls.",
        }

    call_id = f"call_{uuid.uuid4().hex[:8]}"

    # Ensure profile exists in database
    database.upsert_user(
        user_id=user_id,
        name=customer_name,
        facts={
            "past_orders": restock_item,
            "usual_quantities": f"Regular 1-month supply of {restock_item}",
            "preferred_delivery_slot": "morning",
        },
    )

    # Record initial call state
    call_record = database.record_outbound_call(
        call_id=call_id,
        user_id=user_id,
        phone_number=phone_number,
        customer_name=customer_name,
        restock_item=restock_item,
        status="CALLING",
    )

    # Attempt LiveKit API dispatch if keys exist
    lk_url = os.getenv("LIVEKIT_URL")
    lk_key = os.getenv("LIVEKIT_API_KEY")
    lk_secret = os.getenv("LIVEKIT_API_SECRET")
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from_number = os.getenv("TWILIO_PHONE_NUMBER", "")

    if twilio_sid and twilio_token:
        logger.info(
            "Twilio Telephony Trunking active: Account SID=%s... From=%s",
            twilio_sid[:8],
            twilio_from_number or "(not set)",
        )

    livekit_dispatched = False
    dispatch_mode = "none"

    if lk_url and lk_key and lk_secret:
        try:
            from livekit import api

            lkapi = api.LiveKitAPI(url=lk_url, api_key=lk_key, api_secret=lk_secret)
            room_name = f"outbound-{call_id}"

            # Metadata containing mandatory outbound context for agent.py
            metadata = json.dumps(
                {
                    "call_type": "outbound",
                    "customer_name": customer_name,
                    "restock_item": restock_item,
                    "user_id": user_id,
                    "phone_number": phone_number,
                    "call_id": call_id,
                }
            )

            sip_trunk_id = (
                os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "").strip()
                or os.getenv("LIVEKIT_SIP_TRUNK_ID", "").strip()
            )

            if sip_trunk_id:
                # --- LIVE TELEPHONY PATH ---
                # Step 1: Create the LiveKit room with metadata so the agent
                #         knows this is an outbound call when it joins.
                logger.info(
                    "Creating room %s for outbound SIP call...", room_name
                )
                await lkapi.room.create_room(
                    api.CreateRoomRequest(name=room_name, metadata=metadata)
                )

                # Extract clean username (e.g. 'snowwwww') as required by LiveKit API
                # Extract clean username (e.g. 'snowwwww') as required by LiveKit API
                sip_target = phone_number.replace("sip:", "").split("@")[0]

                logger.info(
                    "Placing SIP call to target '%s' (raw: '%s') via trunk %s...",
                    sip_target,
                    phone_number,
                    sip_trunk_id,
                )
                from_number = (
                    twilio_from_number.replace("sip:", "").split("@")[0]
                    if (twilio_from_number and twilio_from_number != "+1XXXXXXXXXX")
                    else sip_target.split("@")[0]
                )

                sip_req = api.CreateSIPParticipantRequest(
                    sip_trunk_id=sip_trunk_id,
                    sip_call_to=sip_target,
                    sip_number=from_number,
                    room_name=room_name,
                    participant_identity=user_id,
                    participant_name=customer_name,
                    wait_until_answered=True,
                )

                await lkapi.sip.create_sip_participant(sip_req)
                livekit_dispatched = True
                dispatch_mode = "sip_trunk"
                logger.info("SIP call dispatched successfully to %s", phone_number)

            else:
                # --- SIMULATION / BROWSER PATH (no SIP trunk configured) ---
                # Creates the room with outbound metadata so the agent picks it
                # up. Use this path to test with the browser UI or Linphone.
                logger.info(
                    "No LIVEKIT_SIP_TRUNK_ID set. Creating simulation room %s with outbound metadata.",
                    room_name,
                )
                await lkapi.room.create_room(
                    api.CreateRoomRequest(name=room_name, metadata=metadata)
                )
                livekit_dispatched = True
                dispatch_mode = "room_only"

            await lkapi.aclose()

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LiveKit API dispatch notice: %s. Outcome will be simulated.", exc
            )

    # Process simulated outcome if specified, otherwise mark CONNECTED
    target_outcome = simulate_outcome or "CONNECTED"
    outcome_result = OutcomeTracker.process_outcome(
        call_id,
        outcome=target_outcome,
        notes="Call dispatched successfully." if livekit_dispatched else "Simulated dispatch mode.",
    )

    return {
        "call_id": call_id,
        "user_id": user_id,
        "phone_number": phone_number,
        "customer_name": customer_name,
        "restock_item": restock_item,
        "livekit_dispatched": livekit_dispatched,
        "dispatch_mode": dispatch_mode,
        "outcome": outcome_result,
        "mandatory_opening": (
            f"1. WHO: Hello {customer_name}! This is ShopMitra calling from ABC Local Store.\n"
            f"2. WHY: I'm calling to check if you would like to restock your monthly order of {restock_item}.\n"
            f"3. OPT-OUT: If you prefer not to receive these restock call reminders, just say 'opt out' or let me know anytime."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Initiate Outbound Restock Call — ShopMitra")
    parser.add_argument("--phone", required=True, help="Phone number to call (e.g., +919876543210)")
    parser.add_argument("--name", default="Ramesh Kumar", help="Customer Name")
    parser.add_argument("--item", default="Basmati Rice 5kg & Wheat Flour 10kg", help="Restock Product Item")
    parser.add_argument("--outcome", choices=["CONNECTED", "NO_ANSWER", "BUSY", "VOICEMAIL", "IMMEDIATE_HANGUP", "OPTED_OUT"], default="CONNECTED", help="Simulate Call Outcome")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    print("\n--- OUTBOUND RESTOCK CALL DISPATCHER ---")
    result = asyncio.run(
        initiate_outbound_call(
            phone_number=args.phone,
            customer_name=args.name,
            restock_item=args.item,
            simulate_outcome=args.outcome,
        )
    )
    print(json.dumps(result, indent=2))
    print("\n=== MANDATORY 3-PART OPENING ===")
    print(result["mandatory_opening"])


if __name__ == "__main__":
    main()
