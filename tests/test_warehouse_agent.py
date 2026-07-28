"""
Tests for Agent 2: Warehouse Operations Agent

Covers:
  1. Cycle sort bin allocation — correctness and annotation
  2. Cycle sort — single item and empty list edge cases
  3. Cycle sort — items with equal pick counts (stability)
  4. Capacity bottleneck detection (> 85 % threshold)
  5. Capacity — no bottlenecks scenario
  6. Pick list optimisation ordering
  7. Happy path — full agent with LLM optimization plan
  8. LLM failure — fallback plan execution
  9. DB failure — error state propagation
  10. State key validation against GlobalLogisticsState
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.warehouse_agent import (
    warehouse_operations_agent,
    cycle_sort_bins,
    detect_capacity_bottlenecks,
    build_optimised_pick_list,
    _avg_utilisation,
    _serialise_rows,
    CAPACITY_THRESHOLD_PCT,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

SAMPLE_WAREHOUSES = [
    {
        "warehouse_id": 1,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
        "city": "Mumbai",
        "total_capacity": 50000,
        "used_capacity": 45000,
        "utilization_pct": Decimal("90.00"),
    },
    {
        "warehouse_id": 2,
        "warehouse_code": "WH-DEL-01",
        "warehouse_name": "Delhi NCR Fulfillment",
        "city": "Gurugram",
        "total_capacity": 35000,
        "used_capacity": 12000,
        "utilization_pct": Decimal("34.29"),
    },
    {
        "warehouse_id": 3,
        "warehouse_code": "WH-BLR-01",
        "warehouse_name": "Bangalore Tech Park",
        "city": "Bangalore",
        "total_capacity": 28000,
        "used_capacity": 26600,
        "utilization_pct": Decimal("95.00"),
    },
]

SAMPLE_TURNOVER_ROWS = [
    {"inventory_id": 1, "warehouse_id": 1, "warehouse_code": "WH-MUM-01", "product_id": 1, "sku": "SKU-A", "product_name": "Item A", "unit_volume_m3": Decimal("0.001"), "quantity_on_hand": 500, "pick_count": 120, "total_picked": 600},
    {"inventory_id": 2, "warehouse_id": 1, "warehouse_code": "WH-MUM-01", "product_id": 2, "sku": "SKU-B", "product_name": "Item B", "unit_volume_m3": Decimal("0.085"), "quantity_on_hand": 80,  "pick_count": 5,   "total_picked": 15},
    {"inventory_id": 3, "warehouse_id": 1, "warehouse_code": "WH-MUM-01", "product_id": 3, "sku": "SKU-C", "product_name": "Item C", "unit_volume_m3": Decimal("0.003"), "quantity_on_hand": 220, "pick_count": 45,  "total_picked": 200},
    {"inventory_id": 4, "warehouse_id": 1, "warehouse_code": "WH-MUM-01", "product_id": 4, "sku": "SKU-D", "product_name": "Item D", "unit_volume_m3": Decimal("0.420"), "quantity_on_hand": 45,  "pick_count": 0,   "total_picked": 0},
    {"inventory_id": 5, "warehouse_id": 1, "warehouse_code": "WH-MUM-01", "product_id": 5, "sku": "SKU-E", "product_name": "Item E", "unit_volume_m3": Decimal("0.002"), "quantity_on_hand": 1200,"pick_count": 300, "total_picked": 1500},
]

SAMPLE_PENDING_PICKS = [
    {"order_id": 1, "order_number": "ORD-001", "order_priority": 2, "promised_at": datetime(2026, 7, 28, tzinfo=timezone.utc), "product_id": 1, "sku": "SKU-A", "product_name": "Item A", "quantity": 3, "warehouse_id": 1, "warehouse_code": "WH-MUM-01"},
    {"order_id": 2, "order_number": "ORD-002", "order_priority": 0, "promised_at": datetime(2026, 7, 29, tzinfo=timezone.utc), "product_id": 3, "sku": "SKU-C", "product_name": "Item C", "quantity": 1, "warehouse_id": 1, "warehouse_code": "WH-MUM-01"},
    {"order_id": 3, "order_number": "ORD-003", "order_priority": 2, "promised_at": datetime(2026, 7, 27, tzinfo=timezone.utc), "product_id": 5, "sku": "SKU-E", "product_name": "Item E", "quantity": 10, "warehouse_id": 1, "warehouse_code": "WH-MUM-01"},
]

SAMPLE_LLM_OPTIMIZATION = {
    "optimization_plan": {
        "space_reallocation": [
            {
                "warehouse_code": "WH-MUM-01",
                "action": "Redistribute 10% of slow-moving Furniture to WH-DEL-01",
                "estimated_freed_m3": 2250,
                "priority": "high",
                "rationale": "Mumbai at 90% capacity; Delhi has 66% headroom.",
            },
        ],
        "bottleneck_warnings": [
            {
                "warehouse_code": "WH-BLR-01",
                "warning": "Bangalore at 95% — critical capacity risk.",
                "recommended_action": "Halt new inbound shipments until capacity drops below 85%.",
            },
        ],
        "bin_layout_suggestions": [
            "Move SKU-E (300 picks) to bin 1 near dispatch zone.",
            "Archive SKU-D (0 picks) to cold storage.",
        ],
    },
    "summary": "Two warehouses require immediate attention. Mumbai and Bangalore are above capacity threshold.",
}

EMPTY_STATE: dict = {"query": "Check warehouse ops", "intent": "warehouse_check"}


# ═══════════════════════════════════════════════════════════════
#  Test 1: Cycle Sort — Correctness
# ═══════════════════════════════════════════════════════════════

class TestCycleSortBins:
    """Verify cycle sort produces correct descending order by pick_count."""

    def test_sorts_by_pick_count_descending(self):
        items = [
            {"sku": "A", "pick_count": 10},
            {"sku": "B", "pick_count": 50},
            {"sku": "C", "pick_count": 5},
            {"sku": "D", "pick_count": 100},
            {"sku": "E", "pick_count": 25},
        ]
        result = cycle_sort_bins(items)

        pick_counts = [item["pick_count"] for item in result]
        assert pick_counts == sorted(pick_counts, reverse=True)

    def test_bin_indices_are_1_based_sequential(self):
        items = [
            {"sku": "X", "pick_count": 3},
            {"sku": "Y", "pick_count": 99},
            {"sku": "Z", "pick_count": 50},
        ]
        result = cycle_sort_bins(items)

        bin_indices = [item["bin_index"] for item in result]
        assert bin_indices == [1, 2, 3]

    def test_needs_move_annotation(self):
        """Items already in correct position should have needs_move=False."""
        items = [
            {"sku": "A", "pick_count": 100},
            {"sku": "B", "pick_count": 50},
            {"sku": "C", "pick_count": 10},
        ]
        result = cycle_sort_bins(items)

        # Already in descending order → no moves needed
        for item in result:
            assert item["needs_move"] is False

    def test_moved_items_have_old_bin_index(self):
        items = [
            {"sku": "A", "pick_count": 1},
            {"sku": "B", "pick_count": 100},
        ]
        result = cycle_sort_bins(items)

        # B (100 picks) should be bin 1, A (1 pick) bin 2
        assert result[0]["sku"] == "B"
        assert result[0]["bin_index"] == 1
        assert result[1]["sku"] == "A"
        assert result[1]["bin_index"] == 2

        # Both should be marked as moved
        moved_items = [i for i in result if i["needs_move"]]
        assert len(moved_items) == 2

    def test_single_item(self):
        items = [{"sku": "SOLO", "pick_count": 42}]
        result = cycle_sort_bins(items)
        assert len(result) == 1
        assert result[0]["bin_index"] == 1
        assert result[0]["needs_move"] is False

    def test_empty_list(self):
        result = cycle_sort_bins([])
        assert result == []

    def test_equal_pick_counts(self):
        """Items with equal pick_count should all get valid bin indices."""
        items = [
            {"sku": "A", "pick_count": 20},
            {"sku": "B", "pick_count": 20},
            {"sku": "C", "pick_count": 20},
        ]
        result = cycle_sort_bins(items)

        assert len(result) == 3
        bin_indices = sorted([item["bin_index"] for item in result])
        assert bin_indices == [1, 2, 3]


# ═══════════════════════════════════════════════════════════════
#  Test 2: Capacity Bottleneck Detection
# ═══════════════════════════════════════════════════════════════

class TestCapacityBottlenecks:
    """Verify bottleneck detection at the 85% threshold."""

    def test_detects_over_85_pct(self):
        warehouses = _serialise_rows(SAMPLE_WAREHOUSES)
        bottlenecks = detect_capacity_bottlenecks(warehouses)

        codes = [b["warehouse_code"] for b in bottlenecks]
        # Mumbai (90%) and Bangalore (95%) should be flagged
        assert "WH-MUM-01" in codes
        assert "WH-BLR-01" in codes
        # Delhi (34%) should NOT be flagged
        assert "WH-DEL-01" not in codes

    def test_severity_critical_above_95(self):
        warehouses = _serialise_rows(SAMPLE_WAREHOUSES)
        bottlenecks = detect_capacity_bottlenecks(warehouses)

        blr = next(b for b in bottlenecks if b["warehouse_code"] == "WH-BLR-01")
        assert blr["severity"] == "critical"

        mum = next(b for b in bottlenecks if b["warehouse_code"] == "WH-MUM-01")
        assert mum["severity"] == "warning"

    def test_no_bottlenecks(self):
        healthy = [
            {"warehouse_id": 1, "warehouse_code": "WH-01", "total_capacity": 1000, "used_capacity": 200, "utilization_pct": 20.0},
        ]
        assert detect_capacity_bottlenecks(healthy) == []

    def test_custom_threshold(self):
        warehouses = [
            {"warehouse_id": 1, "warehouse_code": "WH-01", "total_capacity": 100, "used_capacity": 51, "utilization_pct": 51.0},
        ]
        # 51% > 50% threshold
        assert len(detect_capacity_bottlenecks(warehouses, threshold_pct=50.0)) == 1
        # 51% < 60% threshold
        assert len(detect_capacity_bottlenecks(warehouses, threshold_pct=60.0)) == 0


# ═══════════════════════════════════════════════════════════════
#  Test 3: Pick List Optimisation
# ═══════════════════════════════════════════════════════════════

class TestPickListOptimisation:
    """Verify pick list ordering by priority, SLA, and bin location."""

    def test_sort_order(self):
        bin_map = {
            ("WH-MUM-01", "SKU-A"): 2,
            ("WH-MUM-01", "SKU-C"): 3,
            ("WH-MUM-01", "SKU-E"): 1,
        }
        picks = _serialise_rows(SAMPLE_PENDING_PICKS)
        result = build_optimised_pick_list(picks, bin_map)

        # Order-3 (priority=2, promised=Jul 27) should come first
        assert result[0]["order_number"] == "ORD-003"
        # Order-1 (priority=2, promised=Jul 28) second
        assert result[1]["order_number"] == "ORD-001"
        # Order-2 (priority=0) last
        assert result[2]["order_number"] == "ORD-002"

    def test_pick_sequence_numbers(self):
        bin_map = {}
        picks = _serialise_rows(SAMPLE_PENDING_PICKS)
        result = build_optimised_pick_list(picks, bin_map)

        sequences = [p["pick_sequence"] for p in result]
        assert sequences == [1, 2, 3]

    def test_unknown_bin_goes_last(self):
        bin_map = {("WH-MUM-01", "SKU-A"): 1}  # only SKU-A known
        picks = [
            {"order_id": 1, "order_number": "ORD-X", "order_priority": 1, "promised_at": None, "sku": "SKU-A", "product_name": "A", "quantity": 1, "warehouse_code": "WH-MUM-01"},
            {"order_id": 2, "order_number": "ORD-Y", "order_priority": 1, "promised_at": None, "sku": "SKU-UNKNOWN", "product_name": "Unknown", "quantity": 1, "warehouse_code": "WH-MUM-01"},
        ]
        result = build_optimised_pick_list(picks, bin_map)

        assert result[0]["sku"] == "SKU-A"        # known bin (1)
        assert result[1]["sku"] == "SKU-UNKNOWN"   # unknown bin (9999)

    def test_empty_picks(self):
        result = build_optimised_pick_list([], {})
        assert result == []


# ═══════════════════════════════════════════════════════════════
#  Test 4: Full Agent — Happy Path with LLM
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("agents.warehouse_agent.execute_command", new_callable=AsyncMock)
@patch("agents.warehouse_agent.execute_query", new_callable=AsyncMock)
async def test_happy_path_with_llm(mock_query, mock_log_cmd):
    """Full integration: DB → bin allocation → pick list → LLM plan."""
    # Mock DB returns in call order: warehouses, turnover, pending picks
    mock_query.side_effect = [
        SAMPLE_WAREHOUSES,
        SAMPLE_TURNOVER_ROWS,
        SAMPLE_PENDING_PICKS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_OPTIMIZATION)

    result = await warehouse_operations_agent(EMPTY_STATE, llm_service=mock_llm)

    # LLM was called
    mock_llm.generate.assert_called_once()

    # Structure checks
    assert "warehouse" in result
    wh = result["warehouse"]
    assert "utilization_pct" in wh
    assert isinstance(wh["utilization_pct"], float)
    assert "pending_picks" in wh
    assert "optimization_suggestions" in wh
    assert len(wh["optimization_suggestions"]) > 0

    # Extended data present
    assert "_capacity_report" in wh
    assert "_bottlenecks" in wh
    assert "_bin_allocations" in wh
    assert "_optimization_plan" in wh

    # No error
    assert "error" not in result


# ═══════════════════════════════════════════════════════════════
#  Test 5: LLM Failure → Fallback
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("agents.warehouse_agent.execute_command", new_callable=AsyncMock)
@patch("agents.warehouse_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_fallback(mock_query, mock_log_cmd):
    """Agent degrades gracefully to deterministic fallback when LLM fails."""
    mock_query.side_effect = [
        SAMPLE_WAREHOUSES,
        SAMPLE_TURNOVER_ROWS,
        SAMPLE_PENDING_PICKS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM quota exhausted"))

    result = await warehouse_operations_agent(EMPTY_STATE, llm_service=mock_llm)

    # Should not have a top-level error
    assert "error" not in result

    wh = result["warehouse"]
    assert len(wh["optimization_suggestions"]) > 0

    # Fallback plan should include bottleneck warnings
    opt_plan = wh["_optimization_plan"]["optimization_plan"]
    assert len(opt_plan["bottleneck_warnings"]) > 0
    assert len(opt_plan["bin_layout_suggestions"]) > 0


# ═══════════════════════════════════════════════════════════════
#  Test 6: DB Failure
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("agents.warehouse_agent.execute_command", new_callable=AsyncMock)
@patch("agents.warehouse_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error_state(mock_query, mock_log_cmd):
    """If the DB is unreachable, agent returns an error state."""
    mock_query.side_effect = ConnectionError("Connection refused")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await warehouse_operations_agent(EMPTY_STATE)

    assert "error" in result
    assert "Connection refused" in result["error"]
    assert result["warehouse"]["pending_picks"] == []
    assert result["warehouse"]["optimization_suggestions"] == []


# ═══════════════════════════════════════════════════════════════
#  Test 7: No Active Orders (Empty Pick List)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("agents.warehouse_agent.execute_command", new_callable=AsyncMock)
@patch("agents.warehouse_agent.execute_query", new_callable=AsyncMock)
async def test_no_active_orders(mock_query, mock_log_cmd):
    """When there are no pending orders, pick list should be empty."""
    mock_query.side_effect = [
        SAMPLE_WAREHOUSES,
        SAMPLE_TURNOVER_ROWS,
        [],  # no pending picks
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_OPTIMIZATION)

    result = await warehouse_operations_agent(EMPTY_STATE, llm_service=mock_llm)

    assert result["warehouse"]["pending_picks"] == []
    assert "error" not in result


# ═══════════════════════════════════════════════════════════════
#  Test 8: State Key Validation
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("agents.warehouse_agent.execute_command", new_callable=AsyncMock)
@patch("agents.warehouse_agent.execute_query", new_callable=AsyncMock)
async def test_state_keys_match_global_state(mock_query, mock_log_cmd):
    """Returned dict keys must be valid GlobalLogisticsState keys."""
    mock_query.side_effect = [
        SAMPLE_WAREHOUSES,
        SAMPLE_TURNOVER_ROWS,
        SAMPLE_PENDING_PICKS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_OPTIMIZATION)

    result = await warehouse_operations_agent(EMPTY_STATE, llm_service=mock_llm)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected top-level key '{key}'"

    # Core WarehouseState keys must be present
    wh = result["warehouse"]
    required_keys = {"utilization_pct", "pending_picks", "optimization_suggestions"}
    assert required_keys.issubset(wh.keys()), f"Missing keys: {required_keys - wh.keys()}"


# ═══════════════════════════════════════════════════════════════
#  Test 9: Average Utilisation Helper
# ═══════════════════════════════════════════════════════════════

class TestAvgUtilisation:
    def test_normal(self):
        whs = [{"utilization_pct": 80.0}, {"utilization_pct": 40.0}]
        assert _avg_utilisation(whs) == 60.0

    def test_empty(self):
        assert _avg_utilisation([]) == 0.0

    def test_single(self):
        assert _avg_utilisation([{"utilization_pct": 73.5}]) == 73.5
