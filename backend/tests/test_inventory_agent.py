"""
Tests for Agent 1: Inventory Planning Agent

Covers:
  1. Healthy stock scenario — no low-stock items, LLM is NOT called
  2. Low stock scenario — mock DB returns low-stock rows, mock LLM returns reorder plan
  3. LLM failure fallback — DB returns low-stock rows, LLM raises, deterministic plan used
  4. Priority classification unit tests
  5. Serialisation helper tests
  6. Complete state update structure validation
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.inventory_agent import (
    inventory_planning_agent,
    _classify_priority,
    _build_fallback_plan,
    _serialise_rows,
)


# ── Fixtures ─────────────────────────────────────────────────

SAMPLE_LOW_STOCK_ROWS = [
    {
        "inventory_id": 1,
        "warehouse_id": 1,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
        "product_id": 4,
        "sku": "SKU-HOME-001",
        "product_name": "Ergonomic Office Chair",
        "category": "Furniture",
        "unit_price": Decimal("15999.00"),
        "quantity_on_hand": 3,
        "quantity_reserved": 2,
        "available_qty": 1,
        "reorder_point": 5,
        "reorder_qty": 20,
    },
    {
        "inventory_id": 2,
        "warehouse_id": 3,
        "warehouse_code": "WH-BLR-01",
        "warehouse_name": "Bangalore Tech Park",
        "product_id": 4,
        "sku": "SKU-HOME-001",
        "product_name": "Ergonomic Office Chair",
        "category": "Furniture",
        "unit_price": Decimal("15999.00"),
        "quantity_on_hand": 0,
        "quantity_reserved": 0,
        "available_qty": 0,
        "reorder_point": 5,
        "reorder_qty": 15,
    },
]

SAMPLE_LLM_REORDER_PLAN = {
    "reorder_plan": [
        {
            "inventory_id": 1,
            "warehouse_code": "WH-MUM-01",
            "sku": "SKU-HOME-001",
            "product_name": "Ergonomic Office Chair",
            "current_stock": 3,
            "reorder_point": 5,
            "deficit": 2,
            "recommended_restock_qty": 20,
            "priority": "high",
            "justification": "Stock is critically low at 20% of reorder point. High-value item with strong demand.",
        },
        {
            "inventory_id": 2,
            "warehouse_code": "WH-BLR-01",
            "sku": "SKU-HOME-001",
            "product_name": "Ergonomic Office Chair",
            "current_stock": 0,
            "reorder_point": 5,
            "deficit": 5,
            "recommended_restock_qty": 15,
            "priority": "critical",
            "justification": "Complete stockout. Immediate restocking required to avoid lost sales.",
        },
    ],
    "summary": "2 items require immediate attention. Bangalore warehouse has a full stockout on Ergonomic Office Chairs.",
}

EMPTY_STATE: dict = {"query": "Check inventory", "intent": "inventory_check"}


# ── Test 1: Healthy Stock (No Low-Stock Items) ───────────────

@pytest.mark.asyncio
@patch("agents.inventory_agent.execute_command", new_callable=AsyncMock)
@patch("agents.inventory_agent.execute_query", new_callable=AsyncMock)
async def test_healthy_stock_no_llm_call(mock_query, mock_log_cmd):
    """When all items are above reorder points, the LLM should NOT be invoked."""
    # DB returns no low-stock items
    mock_query.return_value = []
    mock_log_cmd.return_value = "INSERT 0 1"

    # Create a mock LLM service to verify it's never called
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock()

    result = await inventory_planning_agent(EMPTY_STATE, llm_service=mock_llm)

    # LLM must NOT have been called
    mock_llm.generate.assert_not_called()

    # State update should have empty alerts and recommendations
    assert "inventory" in result
    assert result["inventory"]["low_stock_alerts"] == []
    assert result["inventory"]["reorder_recommendations"] == []

    # No error key
    assert "error" not in result


# ── Test 2: Low Stock with LLM Reorder Plan ──────────────────

@pytest.mark.asyncio
@patch("agents.inventory_agent.execute_command", new_callable=AsyncMock)
@patch("agents.inventory_agent.execute_query", new_callable=AsyncMock)
async def test_low_stock_generates_reorder_plan(mock_query, mock_log_cmd):
    """Low-stock items should trigger LLM call and return a properly structured state update."""
    # DB returns low-stock items
    mock_query.return_value = SAMPLE_LOW_STOCK_ROWS
    mock_log_cmd.return_value = "INSERT 0 1"

    # Mock the LLM service
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_REORDER_PLAN)

    result = await inventory_planning_agent(EMPTY_STATE, llm_service=mock_llm)

    # LLM was called exactly once
    mock_llm.generate.assert_called_once()

    # Verify the prompt sent to the LLM contains the SKU
    call_args = mock_llm.generate.call_args
    prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
    assert "SKU-HOME-001" in prompt

    # Validate state structure
    assert "inventory" in result
    inv = result["inventory"]

    # 2 low-stock alerts
    assert len(inv["low_stock_alerts"]) == 2

    # Check alert structure
    alert_0 = inv["low_stock_alerts"][0]
    assert alert_0["inventory_id"] == 1
    assert alert_0["warehouse_code"] == "WH-MUM-01"
    assert alert_0["sku"] == "SKU-HOME-001"
    assert alert_0["quantity_on_hand"] == 3
    assert alert_0["severity"] in ("critical", "high", "medium", "low")

    # Reorder recommendations from LLM
    assert len(inv["reorder_recommendations"]) == 2
    assert inv["reorder_recommendations"][0]["priority"] == "high"
    assert inv["reorder_recommendations"][1]["priority"] == "critical"

    # No error
    assert "error" not in result


# ── Test 3: LLM Failure → Fallback Plan ──────────────────────

@pytest.mark.asyncio
@patch("agents.inventory_agent.execute_command", new_callable=AsyncMock)
@patch("agents.inventory_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_fallback(mock_query, mock_log_cmd):
    """If the LLM call fails, the agent should gracefully fall back to a deterministic reorder plan."""
    mock_query.return_value = SAMPLE_LOW_STOCK_ROWS
    mock_log_cmd.return_value = "INSERT 0 1"

    # LLM raises an exception
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("API quota exceeded"))

    result = await inventory_planning_agent(EMPTY_STATE, llm_service=mock_llm)

    # Should still succeed (no top-level error)
    assert "error" not in result

    inv = result["inventory"]

    # Alerts should still be populated from DB data
    assert len(inv["low_stock_alerts"]) == 2

    # Fallback recommendations should exist
    assert len(inv["reorder_recommendations"]) == 2

    # Verify fallback plan structure
    rec_0 = inv["reorder_recommendations"][0]
    assert "inventory_id" in rec_0
    assert "sku" in rec_0
    assert "deficit" in rec_0
    assert "recommended_restock_qty" in rec_0
    assert rec_0["priority"] in ("critical", "high", "medium", "low")
    assert "justification" in rec_0


# ── Test 4: Priority Classification ──────────────────────────

class TestClassifyPriority:
    """Unit tests for the deterministic priority classifier."""

    def test_critical_stockout(self):
        assert _classify_priority(0, 10) == "critical"

    def test_critical_negative(self):
        assert _classify_priority(-5, 10) == "critical"

    def test_high_priority(self):
        # available_qty = 2, reorder_point = 10 → 2 <= 10*0.25=2.5
        assert _classify_priority(2, 10) == "high"

    def test_medium_priority(self):
        # available_qty = 4, reorder_point = 10 → 4 <= 10*0.5=5.0
        assert _classify_priority(4, 10) == "medium"

    def test_low_priority(self):
        # available_qty = 8, reorder_point = 10 → 8 <= 10
        assert _classify_priority(8, 10) == "low"

    def test_zero_reorder_point(self):
        """Edge case: reorder_point=0 should only trigger critical if qty <= 0."""
        assert _classify_priority(5, 0) == "low"
        assert _classify_priority(0, 0) == "critical"


# ── Test 5: Fallback Plan Builder ────────────────────────────

class TestBuildFallbackPlan:
    """Unit tests for the deterministic fallback plan builder."""

    def test_fallback_plan_structure(self):
        items = [
            {
                "inventory_id": 10,
                "warehouse_code": "WH-DEL-01",
                "sku": "SKU-ELEC-001",
                "product_name": "Wireless Bluetooth Headphones",
                "quantity_on_hand": 5,
                "available_qty": 3,
                "reorder_point": 50,
                "reorder_qty": 200,
            }
        ]
        result = _build_fallback_plan(items)

        assert "reorder_plan" in result
        assert "summary" in result
        assert len(result["reorder_plan"]) == 1

        rec = result["reorder_plan"][0]
        assert rec["inventory_id"] == 10
        assert rec["sku"] == "SKU-ELEC-001"
        assert rec["deficit"] == 45  # 50 - 5
        assert rec["recommended_restock_qty"] == 200  # max(200, 45)
        assert rec["priority"] == "high"  # 3 <= 50*0.25=12.5 → actually 3 <= 12.5 → high

    def test_fallback_plan_deficit_exceeds_reorder_qty(self):
        """When deficit > reorder_qty, recommended_restock_qty should be the deficit."""
        items = [
            {
                "inventory_id": 20,
                "warehouse_code": "WH-MUM-01",
                "sku": "SKU-GROC-001",
                "product_name": "Green Tea",
                "quantity_on_hand": 0,
                "available_qty": 0,
                "reorder_point": 100,
                "reorder_qty": 50,  # Less than deficit of 100
            }
        ]
        result = _build_fallback_plan(items)
        rec = result["reorder_plan"][0]
        assert rec["deficit"] == 100
        assert rec["recommended_restock_qty"] == 100  # max(50, 100)
        assert rec["priority"] == "critical"


# ── Test 6: Serialisation Helper ─────────────────────────────

class TestSerialiseRows:
    """Unit tests for asyncpg row serialisation."""

    def test_decimal_conversion(self):
        rows = [{"price": Decimal("29.99"), "name": "Widget"}]
        result = _serialise_rows(rows)
        assert result[0]["price"] == 29.99
        assert isinstance(result[0]["price"], float)

    def test_datetime_conversion(self):
        dt = datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)
        rows = [{"created_at": dt, "id": 1}]
        result = _serialise_rows(rows)
        assert result[0]["created_at"] == "2026-07-27T10:00:00+00:00"
        assert isinstance(result[0]["created_at"], str)

    def test_passthrough_types(self):
        rows = [{"id": 42, "name": "Test", "active": True}]
        result = _serialise_rows(rows)
        assert result[0] == {"id": 42, "name": "Test", "active": True}

    def test_empty_rows(self):
        assert _serialise_rows([]) == []


# ── Test 7: DB Failure Propagation ───────────────────────────

@pytest.mark.asyncio
@patch("agents.inventory_agent.execute_command", new_callable=AsyncMock)
@patch("agents.inventory_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error_state(mock_query, mock_log_cmd):
    """If the DB query fails, the agent should return an error in the state."""
    mock_query.side_effect = ConnectionError("Database unreachable")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await inventory_planning_agent(EMPTY_STATE)

    assert "error" in result
    assert "Database unreachable" in result["error"]
    assert result["inventory"]["low_stock_alerts"] == []
    assert result["inventory"]["reorder_recommendations"] == []


# ── Test 8: State Update Keys Match GlobalLogisticsState ─────

@pytest.mark.asyncio
@patch("agents.inventory_agent.execute_command", new_callable=AsyncMock)
@patch("agents.inventory_agent.execute_query", new_callable=AsyncMock)
async def test_state_update_keys_valid(mock_query, mock_log_cmd):
    """The returned dict keys must be valid GlobalLogisticsState keys."""
    mock_query.return_value = []
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await inventory_planning_agent(EMPTY_STATE)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected key '{key}' in state update"

    # inventory sub-state keys
    valid_inv_keys = {
        "warehouse_id", "product_id",
        "quantity_on_hand", "quantity_reserved",
        "reorder_point", "reorder_qty",
        "low_stock_alerts", "reorder_recommendations",
    }
    for key in result["inventory"].keys():
        assert key in valid_inv_keys, f"Unexpected key '{key}' in inventory sub-state"
