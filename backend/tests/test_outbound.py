"""
test_outbound.py — Tests for Day 6 Outbound Calls and Outcome Handling
"""

import os
from unittest.mock import patch

import pytest

from database import (
    get_outbound_call,
    is_user_opted_out,
    list_outbound_calls,
    record_outbound_call,
    set_user_opt_out,
    update_outbound_call_outcome,
)
from outbound_caller import OutcomeTracker, initiate_outbound_call


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_shopmitra.db"
    with patch("database._DB_PATH", db_file), patch("database._conn", None):
        yield


def test_opt_out_management():
    user_id = "test_user_opt"
    assert not is_user_opted_out(user_id)

    set_user_opt_out(user_id, True)
    assert is_user_opted_out(user_id)

    set_user_opt_out(user_id, False)
    assert not is_user_opted_out(user_id)


def test_record_and_update_outbound_call():
    call_id = "test_call_001"
    user_id = "customer_123"

    call = record_outbound_call(
        call_id=call_id,
        user_id=user_id,
        phone_number="+919876543210",
        customer_name="Ramesh",
        restock_item="Basmati Rice 5kg",
        status="CALLING",
    )

    assert call["call_id"] == call_id
    assert call["status"] == "CALLING"

    updated = update_outbound_call_outcome(
        call_id=call_id,
        status="CONNECTED",
        outcome_notes="Call completed successfully.",
    )
    assert updated["status"] == "CONNECTED"
    assert "completed successfully" in updated["outcome_notes"]


def test_outcome_tracker_retry_policies():
    call_id = "test_retry_call"
    user_id = "user_retry"

    record_outbound_call(
        call_id=call_id,
        user_id=user_id,
        phone_number="+919876543210",
        customer_name="Priya",
        restock_item="Wheat Flour 10kg",
        status="CALLING",
        attempt_count=1,
    )

    # Test NO_ANSWER retry calculation (30 mins delay)
    result = OutcomeTracker.process_outcome(call_id, "NO_ANSWER")
    assert result["status"] == "NO_ANSWER"
    assert result["next_retry_at"] is not None
    assert "Next retry scheduled" in result["outcome_notes"]

    # Test BUSY retry calculation (15 mins delay)
    result_busy = OutcomeTracker.process_outcome(call_id, "BUSY")
    assert result_busy["status"] == "BUSY"
    assert result_busy["next_retry_at"] is not None

    # Test VOICEMAIL policy (no retry, message left)
    result_vm = OutcomeTracker.process_outcome(call_id, "VOICEMAIL")
    assert result_vm["status"] == "VOICEMAIL"
    assert result_vm["next_retry_at"] is None

    # Test IMMEDIATE_HANGUP policy (no retry today)
    result_hangup = OutcomeTracker.process_outcome(call_id, "IMMEDIATE_HANGUP")
    assert result_hangup["status"] == "IMMEDIATE_HANGUP"
    assert result_hangup["next_retry_at"] is None


@pytest.mark.asyncio
async def test_initiate_outbound_call():
    result = await initiate_outbound_call(
        phone_number="+919876543210",
        customer_name="Ramesh",
        restock_item="Basmati Rice 5kg",
        simulate_outcome="CONNECTED",
    )

    assert result["call_id"].startswith("call_")
    assert result["customer_name"] == "Ramesh"
    assert "Hello Ramesh! This is ShopMitra" in result["mandatory_opening"]
    assert "opt out" in result["mandatory_opening"]
