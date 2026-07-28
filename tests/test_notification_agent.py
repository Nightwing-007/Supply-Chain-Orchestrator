"""
Tests for Agent 6: Customer Notification Agent

Covers:
  1. Template generator correctness (apologetic, enthusiastic, informative tones)
  2. Query identification of queued notifications from mocked DB
  3. Happy path -- full agent with LLM email & SMS communication plan
  4. LLM failure -- deterministic fallback template execution
  5. Empty state / no queued notifications handling
  6. DB failure -- error state propagation
  7. State key validation against GlobalLogisticsState
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.notification_agent import (
    customer_notification_agent,
    build_templated_notification,
    _serialise_rows,
)


# =============================================================
#  Fixtures
# =============================================================

SAMPLE_QUEUED_NOTIFICATIONS = [
    {
        "notification_id": 101,
        "order_id": 1,
        "channel": "email",
        "recipient": "arjun@example.com",
        "subject": "Order Confirmation",
        "body": "Your order has been placed.",
        "notification_status": "queued",
        "order_number": "ORD-2026-00001",
        "customer_name": "Arjun Mehta",
        "customer_email": "arjun@example.com",
        "customer_phone": "+91-98765-43210",
        "delivery_address": "12 MG Road, Indiranagar, Bangalore",
        "order_status": "confirmed",
        "promised_at": datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc),
        "total_amount": Decimal("38498.00"),
    }
]

SAMPLE_RECENT_ORDERS = [
    {
        "order_id": 3,
        "order_number": "ORD-2026-00003",
        "customer_name": "Rohan Kapoor",
        "customer_email": "rohan@example.com",
        "customer_phone": "+91-87654-32109",
        "delivery_address": "5 Marine Drive, Churchgate, Mumbai",
        "order_status": "picking",
        "promised_at": datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc),
        "total_amount": Decimal("5999.00"),
    }
]

SAMPLE_LLM_COMMUNICATION_PLAN = {
    "communication_plan": {
        "email": {
            "subject": "Order #ORD-2026-00001 Confirmed - Preparing for Dispatch!",
            "body": (
                "Dear Arjun Mehta,\n\n"
                "Thank you for your order! We are delighted to confirm that your order #ORD-2026-00001 "
                "is currently being packed at our Bangalore hub.\n\n"
                "Estimated Delivery: July 30, 2026.\n\n"
                "Warm regards,\nCustomer Success Team"
            ),
        },
        "sms": {
            "body": "Order #ORD-2026-00001 confirmed! Packed at Bangalore hub. Estimated delivery: Jul 30.",
        },
        "tone": "enthusiastic",
        "action_taken": "Sent confirmation email and short SMS.",
    },
    "summary": "Drafted enthusiastic confirmation communication for Arjun Mehta.",
}

EMPTY_STATE: dict = {"query": "Send customer notification", "intent": "customer_notification"}


# =============================================================
#  Test 1: Rule-Based Template Generator
# =============================================================

class TestTemplateGenerator:
    """Unit tests for build_templated_notification."""

    def test_apologetic_tone_for_delay(self):
        res = build_templated_notification(
            order_number="ORD-100",
            customer_name="Alice",
            order_status="exception",
            event_type="weather_delay",
            reason="Monsoon rain flooding",
        )
        assert res["tone"] == "apologetic"
        assert "ORD-100" in res["email_subject"]
        assert "Alice" in res["email_body"]
        assert "Monsoon rain flooding" in res["email_body"]
        assert len(res["sms_body"]) <= 160

    def test_enthusiastic_tone_for_delivery(self):
        res = build_templated_notification(
            order_number="ORD-200",
            customer_name="Bob",
            order_status="delivered",
        )
        assert res["tone"] == "enthusiastic"
        assert "ORD-200" in res["email_subject"]
        assert "delivered" in res["email_body"].lower()
        assert len(res["sms_body"]) <= 160

    def test_informative_tone_default(self):
        res = build_templated_notification(
            order_number="ORD-300",
            customer_name="Charlie",
            order_status="pending",
        )
        assert res["tone"] == "informative"
        assert "ORD-300" in res["email_subject"]
        assert "pending" in res["email_body"].lower()

    def test_sms_length_capped_at_160(self):
        res = build_templated_notification(
            order_number="ORD-999999999",
            customer_name="Very Long Customer Name " * 5,
            order_status="delay_due_to_unforeseen_highway_closure",
            reason="Extremely long reason sentence describing in detail the exact roadblock and delays encountered.",
        )
        assert len(res["sms_body"]) <= 160


# =============================================================
#  Test 2: Identification of Pending Notifications from DB
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_identifies_pending_notifications(mock_query, mock_log_cmd):
    """Agent queries pending notifications table and processes queued item."""
    mock_query.side_effect = [
        SAMPLE_QUEUED_NOTIFICATIONS,
    ]
    mock_log_cmd.return_value = "UPDATE 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_COMMUNICATION_PLAN)

    result = await customer_notification_agent(EMPTY_STATE, llm_service=mock_llm)

    mock_llm.generate.assert_called_once()
    assert "notification" in result
    notif = result["notification"]
    assert notif["notification_id"] == 101
    assert notif["customer_name"] == "Arjun Mehta"
    assert notif["customer_email"] == "arjun@example.com"
    assert "error" not in result


# =============================================================
#  Test 3: Happy Path -- LLM Drafts Customized Email & SMS
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_happy_path_llm_drafting(mock_query, mock_log_cmd):
    """Full integration: DB -> LLM Communication Plan -> DB status update."""
    mock_query.side_effect = [
        SAMPLE_QUEUED_NOTIFICATIONS,
    ]
    mock_log_cmd.return_value = "UPDATE 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_COMMUNICATION_PLAN)

    result = await customer_notification_agent(EMPTY_STATE, llm_service=mock_llm)

    notif = result["notification"]
    assert notif["_email_subject"] == "Order #ORD-2026-00001 Confirmed - Preparing for Dispatch!"
    assert "Arjun Mehta" in notif["message_body"]
    assert notif["_tone"] == "enthusiastic"
    assert "ORD-2026-00001" in notif["_sms_body"]
    assert "error" not in result


# =============================================================
#  Test 4: LLM Failure -> Deterministic Fallback
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_fallback(mock_query, mock_log_cmd):
    """When LLM fails, agent uses rule-based notification template."""
    mock_query.side_effect = [
        SAMPLE_QUEUED_NOTIFICATIONS,
    ]
    mock_log_cmd.return_value = "UPDATE 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM API quota exceeded"))

    result = await customer_notification_agent(EMPTY_STATE, llm_service=mock_llm)

    assert "error" not in result
    notif = result["notification"]

    assert notif["customer_name"] == "Arjun Mehta"
    assert "ORD-2026-00001" in notif["_email_subject"]
    assert "ORD-2026-00001" in notif["_sms_body"]
    assert notif["_tone"] in ("informative", "enthusiastic", "apologetic")


# =============================================================
#  Test 5: Empty Queue Scenario (Recent Orders Fallback)
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_empty_queue_uses_recent_orders(mock_query, mock_log_cmd):
    """When no notifications are queued, agent uses recent order data."""
    mock_query.side_effect = [
        [],  # no queued notifications
        SAMPLE_RECENT_ORDERS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_COMMUNICATION_PLAN)

    result = await customer_notification_agent(EMPTY_STATE, llm_service=mock_llm)

    assert "error" not in result
    notif = result["notification"]
    assert notif["customer_name"] == "Rohan Kapoor"
    assert notif["notification_id"] == 0  # not from queued table


# =============================================================
#  Test 6: DB Failure Propagation
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error(mock_query, mock_log_cmd):
    """DB connection failure propagates as error in state."""
    mock_query.side_effect = ConnectionError("PostgreSQL connection refused")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await customer_notification_agent(EMPTY_STATE)

    assert "error" in result
    assert "PostgreSQL connection refused" in result["error"]
    assert result["notification"]["customer_name"] == "UNKNOWN"


# =============================================================
#  Test 7: State Key Validation
# =============================================================

@pytest.mark.asyncio
@patch("agents.notification_agent.execute_command", new_callable=AsyncMock)
@patch("agents.notification_agent.execute_query", new_callable=AsyncMock)
async def test_state_keys_match_global_state(mock_query, mock_log_cmd):
    """Returned state keys must be compatible with GlobalLogisticsState."""
    mock_query.side_effect = [
        SAMPLE_QUEUED_NOTIFICATIONS,
    ]
    mock_log_cmd.return_value = "UPDATE 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_COMMUNICATION_PLAN)

    result = await customer_notification_agent(EMPTY_STATE, llm_service=mock_llm)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected top-level key '{key}'"

    notif_state = result["notification"]
    required_keys = {
        "order_id", "customer_name", "customer_email", "customer_phone",
        "channel", "event_type", "message_body", "notification_id",
    }
    assert required_keys.issubset(notif_state.keys()), f"Missing keys: {required_keys - notif_state.keys()}"
