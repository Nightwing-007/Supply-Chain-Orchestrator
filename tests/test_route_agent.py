"""
Tests for Agent 4: Route Optimization Agent

Covers:
  1. Haversine distance math correctness (zero, short, known distances)
  2. Nearest Neighbor TSP algorithm sequence generation
  3. Nearest Neighbor edge cases (single stop, empty list)
  4. Happy path -- full agent with LLM dynamic dispatch adjustment
  5. LLM failure -- deterministic Nearest Neighbor fallback
  6. Empty delivery stops scenario
  7. DB failure -- error state propagation
  8. State key validation against GlobalLogisticsState
  9. Fallback plan structure verification
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.route_agent import (
    route_optimization_agent,
    haversine_distance,
    nearest_neighbor_route,
    _build_fallback_route_plan,
    _serialise_rows,
    AVERAGE_SPEED_KMH,
    STOP_SERVICE_TIME_MIN,
)


# =============================================================
#  Fixtures
# =============================================================

SAMPLE_ORIGIN_WAREHOUSE = [
    {
        "warehouse_id": 1,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
        "latitude": Decimal("19.0760"),
        "longitude": Decimal("72.8777"),
    }
]

SAMPLE_VEHICLES = [
    {
        "vehicle_id": 1,
        "registration": "MH-04-AB-1234",
        "vehicle_type": "truck",
        "vehicle_status": "available",
        "capacity_kg": Decimal("8000.00"),
        "capacity_m3": Decimal("40.00"),
        "current_lat": Decimal("19.0760"),
        "current_lon": Decimal("72.8777"),
        "warehouse_id": 1,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
        "warehouse_lat": Decimal("19.0760"),
        "warehouse_lon": Decimal("72.8777"),
    }
]

# Mumbai delivery locations:
# 1. Marine Drive (18.9440, 72.8237) ~ 15 km from origin
# 2. Indiranagar Bangalore (12.9784, 77.6408) ~ 840 km from origin
# 3. Dadar Mumbai (19.0178, 72.8478) ~ 7 km from origin
SAMPLE_DELIVERY_STOPS = [
    {
        "order_id": 1,
        "order_number": "ORD-2026-00001",
        "customer_name": "Arjun Mehta",
        "delivery_address": "12 MG Road",
        "delivery_city": "Bangalore",
        "latitude": Decimal("12.9784"),
        "longitude": Decimal("77.6408"),
        "order_priority": 1,
        "order_status": "confirmed",
        "promised_at": datetime(2026, 7, 29, tzinfo=timezone.utc),
    },
    {
        "order_id": 2,
        "order_number": "ORD-2026-00002",
        "customer_name": "Rohan Kapoor",
        "delivery_address": "5 Marine Drive",
        "delivery_city": "Mumbai",
        "latitude": Decimal("18.9440"),
        "longitude": Decimal("72.8237"),
        "order_priority": 2,
        "order_status": "picking",
        "promised_at": datetime(2026, 7, 28, tzinfo=timezone.utc),
    },
    {
        "order_id": 3,
        "order_number": "ORD-2026-00003",
        "customer_name": "Priya Sharma",
        "delivery_address": "45 Dadar West",
        "delivery_city": "Mumbai",
        "latitude": Decimal("19.0178"),
        "longitude": Decimal("72.8478"),
        "order_priority": 0,
        "order_status": "pending",
        "promised_at": datetime(2026, 7, 30, tzinfo=timezone.utc),
    },
]

SAMPLE_LLM_ADJUSTMENT_PLAN = {
    "route_adjustment_plan": {
        "optimized_stop_sequence": [
            {
                "stop_order": 1,
                "order_id": 3,
                "order_number": "ORD-2026-00003",
                "customer_name": "Priya Sharma",
                "delivery_address": "45 Dadar West",
                "reason_for_sequence": "Closest to origin hub (7 km). Avoids Dadar peak traffic.",
            },
            {
                "stop_order": 2,
                "order_id": 2,
                "order_number": "ORD-2026-00002",
                "customer_name": "Rohan Kapoor",
                "delivery_address": "5 Marine Drive",
                "reason_for_sequence": "High priority order (Priority 2). High-tide surge expected later.",
            },
            {
                "stop_order": 3,
                "order_id": 1,
                "order_number": "ORD-2026-00001",
                "customer_name": "Arjun Mehta",
                "delivery_address": "12 MG Road",
                "reason_for_sequence": "Interstate long haul destination.",
            },
        ],
        "avoided_hazards": [
            {
                "hazard_type": "traffic_congestion",
                "location": "Dadar Junction",
                "action_taken": "Scheduled Dadar stop first to clear before 09:00 AM rush hour.",
            }
        ],
        "estimated_delay_warnings": [
            "Monsoon showers on Pune-Bangalore highway may add 45 minutes.",
        ],
        "revised_total_distance_km": 875.40,
        "revised_total_duration_min": 1380,
    },
    "summary": "Re-ordered stops to clear local Mumbai deliveries before morning rush before long-haul dispatch.",
}

EMPTY_STATE: dict = {"query": "Optimize route", "intent": "route_optimization"}


# =============================================================
#  Test 1: Haversine Distance Math
# =============================================================

class TestHaversineDistance:
    """Unit tests for the Haversine distance formula."""

    def test_same_point_is_zero(self):
        dist = haversine_distance(19.0760, 72.8777, 19.0760, 72.8777)
        assert dist == 0.0

    def test_known_distance_mumbai_to_delhi(self):
        """Mumbai (19.0760, 72.8777) to Delhi (28.7041, 77.1025) is ~1145-1160 km."""
        dist = haversine_distance(19.0760, 72.8777, 28.7041, 77.1025)
        assert 1140.0 <= dist <= 1170.0

    def test_short_distance_in_mumbai(self):
        """Mumbai Hub (19.0760, 72.8777) to Dadar (19.0178, 72.8478) is ~7-8 km."""
        dist = haversine_distance(19.0760, 72.8777, 19.0178, 72.8478)
        assert 6.0 <= dist <= 9.0

    def test_symmetry(self):
        d1 = haversine_distance(19.0760, 72.8777, 12.9716, 77.5946)
        d2 = haversine_distance(12.9716, 77.5946, 19.0760, 72.8777)
        assert d1 == d2


# =============================================================
#  Test 2: Nearest Neighbor TSP Heuristic
# =============================================================

class TestNearestNeighborRoute:
    """Unit tests for the Nearest Neighbor TSP algorithm."""

    def test_greedy_sequencing(self):
        origin = {"latitude": 19.0760, "longitude": 72.8777}  # Mumbai Hub
        stops = [
            {"order_id": 1, "order_number": "ORD-BLR", "latitude": 12.9784, "longitude": 77.6408},  # ~840km
            {"order_id": 2, "order_number": "ORD-DADAR", "latitude": 19.0178, "longitude": 72.8478}, # ~7km
            {"order_id": 3, "order_number": "ORD-MARINE", "latitude": 18.9440, "longitude": 72.8237},# ~15km
        ]

        route, total_dist, total_dur = nearest_neighbor_route(origin, stops)

        assert len(route) == 3
        # From Hub (19.076), closest is Dadar (19.0178)
        assert route[0]["order_number"] == "ORD-DADAR"
        assert route[0]["stop_order"] == 1

        # From Dadar (19.0178), closest is Marine Drive (18.9440)
        assert route[1]["order_number"] == "ORD-MARINE"
        assert route[1]["stop_order"] == 2

        # Last is Bangalore
        assert route[2]["order_number"] == "ORD-BLR"
        assert route[2]["stop_order"] == 3

        # Cumulative distance should be monotonically increasing
        assert route[0]["cumulative_distance_km"] < route[1]["cumulative_distance_km"] < route[2]["cumulative_distance_km"]

    def test_single_stop(self):
        origin = {"latitude": 19.0760, "longitude": 72.8777}
        stops = [{"order_id": 10, "order_number": "ORD-1", "latitude": 19.0178, "longitude": 72.8478}]

        route, total_dist, total_dur = nearest_neighbor_route(origin, stops)

        assert len(route) == 1
        assert route[0]["stop_order"] == 1
        assert route[0]["leg_distance_km"] > 0
        assert total_dist == route[0]["leg_distance_km"]
        assert total_dur > 0

    def test_empty_stops(self):
        origin = {"latitude": 19.0760, "longitude": 72.8777}
        route, total_dist, total_dur = nearest_neighbor_route(origin, [])

        assert route == []
        assert total_dist == 0.0
        assert total_dur == 0


# =============================================================
#  Test 3: Full Agent -- Happy Path with LLM Adjustment
# =============================================================

@pytest.mark.asyncio
@patch("agents.route_agent.execute_command", new_callable=AsyncMock)
@patch("agents.route_agent.execute_query", new_callable=AsyncMock)
async def test_happy_path_with_llm(mock_query, mock_log_cmd):
    """Full pipeline: DB -> Nearest Neighbor -> LLM route adjustment."""
    mock_query.side_effect = [
        SAMPLE_ORIGIN_WAREHOUSE,
        SAMPLE_VEHICLES,
        SAMPLE_DELIVERY_STOPS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_ADJUSTMENT_PLAN)

    result = await route_optimization_agent(EMPTY_STATE, llm_service=mock_llm)

    mock_llm.generate.assert_called_once()

    assert "route" in result
    route_state = result["route"]
    assert route_state["route_id"] == 1
    assert route_state["vehicle_id"] == 1
    assert route_state["origin_warehouse_id"] == 1
    assert len(route_state["stops"]) == 3
    assert route_state["optimized_order"] == [3, 2, 1]
    assert route_state["total_distance_km"] == 875.40
    assert route_state["total_duration_min"] == 1380

    assert "_environmental_constraints" in route_state
    assert "_adjustment_plan" in route_state
    assert "error" not in result


# =============================================================
#  Test 4: LLM Failure -> Nearest Neighbor Fallback
# =============================================================

@pytest.mark.asyncio
@patch("agents.route_agent.execute_command", new_callable=AsyncMock)
@patch("agents.route_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_fallback(mock_query, mock_log_cmd):
    """When LLM fails, agent returns pure Nearest Neighbor route."""
    mock_query.side_effect = [
        SAMPLE_ORIGIN_WAREHOUSE,
        SAMPLE_VEHICLES,
        SAMPLE_DELIVERY_STOPS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM API Timeout"))

    result = await route_optimization_agent(EMPTY_STATE, llm_service=mock_llm)

    assert "error" not in result
    route_state = result["route"]

    # Nearest Neighbor sequence order IDs for sample: Dadar(3), Marine Drive(2), Bangalore(1)
    assert route_state["optimized_order"] == [3, 2, 1]
    assert len(route_state["stops"]) == 3
    assert route_state["total_distance_km"] > 0

    plan = route_state["_adjustment_plan"]["route_adjustment_plan"]
    assert "Nearest Neighbor" in plan["estimated_delay_warnings"][0]


# =============================================================
#  Test 5: No Delivery Stops Scenario
# =============================================================

@pytest.mark.asyncio
@patch("agents.route_agent.execute_command", new_callable=AsyncMock)
@patch("agents.route_agent.execute_query", new_callable=AsyncMock)
async def test_no_delivery_stops(mock_query, mock_log_cmd):
    """When no orders/stops are pending, return empty route."""
    mock_query.side_effect = [
        SAMPLE_ORIGIN_WAREHOUSE,
        SAMPLE_VEHICLES,
        [],  # no stops
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()

    result = await route_optimization_agent(EMPTY_STATE, llm_service=mock_llm)

    mock_llm.generate.assert_not_called()
    assert result["route"]["stops"] == []
    assert result["route"]["total_distance_km"] == 0.0
    assert result["route"]["optimized_order"] == []
    assert "error" not in result


# =============================================================
#  Test 6: DB Failure
# =============================================================

@pytest.mark.asyncio
@patch("agents.route_agent.execute_command", new_callable=AsyncMock)
@patch("agents.route_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error(mock_query, mock_log_cmd):
    """DB connection failure propagates error in state."""
    mock_query.side_effect = ConnectionError("Database pool exhausted")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await route_optimization_agent(EMPTY_STATE)

    assert "error" in result
    assert "Database pool exhausted" in result["error"]
    assert result["route"]["stops"] == []
    assert result["route"]["total_distance_km"] == 0.0


# =============================================================
#  Test 7: State Key Validation
# =============================================================

@pytest.mark.asyncio
@patch("agents.route_agent.execute_command", new_callable=AsyncMock)
@patch("agents.route_agent.execute_query", new_callable=AsyncMock)
async def test_state_keys_match_global_state(mock_query, mock_log_cmd):
    """Returned state keys must be compatible with GlobalLogisticsState."""
    mock_query.side_effect = [
        SAMPLE_ORIGIN_WAREHOUSE,
        SAMPLE_VEHICLES,
        SAMPLE_DELIVERY_STOPS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_ADJUSTMENT_PLAN)

    result = await route_optimization_agent(EMPTY_STATE, llm_service=mock_llm)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected top-level key '{key}'"

    route_state = result["route"]
    required_keys = {
        "route_id", "vehicle_id", "origin_warehouse_id",
        "stops", "total_distance_km", "total_duration_min", "optimized_order",
    }
    assert required_keys.issubset(route_state.keys()), f"Missing keys: {required_keys - route_state.keys()}"


# =============================================================
#  Test 8: Fallback Plan Helper
# =============================================================

class TestFallbackRoutePlan:
    """Verify fallback plan generator structure."""

    def test_fallback_structure(self):
        baseline = [
            {
                "stop_order": 1,
                "order_id": 101,
                "order_number": "ORD-101",
                "customer_name": "Test Cust",
                "delivery_address": "123 Street",
                "leg_distance_km": 5.2,
            }
        ]
        result = _build_fallback_route_plan(baseline, 5.2, 22)

        assert "route_adjustment_plan" in result
        plan = result["route_adjustment_plan"]
        assert len(plan["optimized_stop_sequence"]) == 1
        assert plan["revised_total_distance_km"] == 5.2
        assert plan["revised_total_duration_min"] == 22
        assert plan["optimized_stop_sequence"][0]["order_id"] == 101
