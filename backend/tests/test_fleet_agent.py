"""
Tests for Agent 5: Fleet Management Agent

Covers:
  1. Telemetry calculation (days since service, mileage, fuel level)
  2. Threshold flagging logic (> 10,000 km, > 90 days, low fuel)
  3. Utilization rate percentage calculation
  4. Happy path -- full agent with LLM maintenance plan
  5. LLM failure -- deterministic fallback (strict grounding rule)
  6. Empty vehicles list scenario
  7. DB failure -- error state propagation
  8. State key validation against GlobalLogisticsState
  9. Fallback fleet plan generator correctness
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.fleet_agent import (
    fleet_management_agent,
    calculate_vehicle_telemetry,
    flag_maintenance_thresholds,
    build_fallback_fleet_plan,
    _serialise_rows,
    CRITICAL_MILEAGE_KM,
    CRITICAL_DAYS_LIMIT,
    LOW_FUEL_THRESHOLD_PCT,
)


# =============================================================
#  Fixtures
# =============================================================

NOW = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_VEHICLES = [
    # Vehicle 1: Healthy available vehicle
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
        "fuel_level_pct": Decimal("85.00"),
        "mileage_km": Decimal("4500.00"),
        "last_maintenance": NOW - timedelta(days=30),
        "next_maintenance": NOW + timedelta(days=60),
        "is_active": True,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
    },
    # Vehicle 2: Over mileage (>10,000 km)
    {
        "vehicle_id": 2,
        "registration": "MH-04-CD-5678",
        "vehicle_type": "van",
        "vehicle_status": "in_transit",
        "capacity_kg": Decimal("2500.00"),
        "capacity_m3": Decimal("12.00"),
        "current_lat": Decimal("19.0760"),
        "current_lon": Decimal("72.8777"),
        "warehouse_id": 1,
        "fuel_level_pct": Decimal("60.00"),
        "mileage_km": Decimal("12500.00"),  # Exceeds 10,000 km
        "last_maintenance": NOW - timedelta(days=40),
        "next_maintenance": NOW - timedelta(days=5),
        "is_active": True,
        "warehouse_code": "WH-MUM-01",
        "warehouse_name": "Mumbai Central Hub",
    },
    # Vehicle 3: Over days (>90 days)
    {
        "vehicle_id": 3,
        "registration": "DL-01-EF-9012",
        "vehicle_type": "truck",
        "vehicle_status": "available",
        "capacity_kg": Decimal("8000.00"),
        "capacity_m3": Decimal("40.00"),
        "current_lat": Decimal("28.7041"),
        "current_lon": Decimal("77.1025"),
        "warehouse_id": 2,
        "fuel_level_pct": Decimal("75.00"),
        "mileage_km": Decimal("3000.00"),
        "last_maintenance": NOW - timedelta(days=100),  # Exceeds 90 days
        "next_maintenance": NOW - timedelta(days=10),
        "is_active": True,
        "warehouse_code": "WH-DEL-01",
        "warehouse_name": "Delhi NCR Fulfillment",
    },
    # Vehicle 4: Low fuel (<15%)
    {
        "vehicle_id": 4,
        "registration": "KA-01-GH-3456",
        "vehicle_type": "van",
        "vehicle_status": "available",
        "capacity_kg": Decimal("2500.00"),
        "capacity_m3": Decimal("12.00"),
        "current_lat": Decimal("12.9716"),
        "current_lon": Decimal("77.5946"),
        "warehouse_id": 3,
        "fuel_level_pct": Decimal("10.00"),  # Low fuel < 15%
        "mileage_km": Decimal("2000.00"),
        "last_maintenance": NOW - timedelta(days=15),
        "next_maintenance": NOW + timedelta(days=75),
        "is_active": True,
        "warehouse_code": "WH-BLR-01",
        "warehouse_name": "Bangalore Tech Park",
    },
]

SAMPLE_LLM_FLEET_PLAN = {
    "maintenance_plan": {
        "categorized_vehicles": [
            {
                "vehicle_id": 2,
                "registration": "MH-04-CD-5678",
                "action_category": "Immediate Grounding",
                "reallocation_note": "Reallocate active in-transit load to Truck MH-04-AB-1234 upon arrival.",
                "justification": "Mileage at 12,500 km exceeds critical 10,000 km maintenance limit.",
            },
            {
                "vehicle_id": 3,
                "registration": "DL-01-EF-9012",
                "action_category": "Immediate Grounding",
                "reallocation_note": "Ground at Delhi Hub until full service inspection.",
                "justification": "Last service was 100 days ago (exceeds 90-day maximum interval).",
            },
            {
                "vehicle_id": 4,
                "registration": "KA-01-GH-3456",
                "action_category": "Safe for Local Routes Only",
                "reallocation_note": "Refuel immediately at Bangalore Tech Park hub station.",
                "justification": "Fuel level at 10% requires immediate refueling before dispatch.",
            },
        ],
        "fleet_health_summary": "25% of fleet is currently in transit. 3 of 4 vehicles require operational intervention.",
        "recommendations": [
            "Perform immediate maintenance on MH-04-CD-5678 and DL-01-EF-9012.",
            "Refuel KA-01-GH-3456 before assigning next local delivery route.",
        ],
    },
    "summary": "2 vehicles grounded for exceeding maintenance thresholds. 1 vehicle routed for immediate refueling.",
}

EMPTY_STATE: dict = {"query": "Check fleet status", "intent": "fleet_management"}


# =============================================================
#  Test 1: Telemetry Calculations
# =============================================================

class TestTelemetryCalculations:
    """Unit tests for calculate_vehicle_telemetry."""

    def test_days_since_service_accurate(self):
        v = {
            "registration": "TEST-01",
            "last_maintenance": NOW - timedelta(days=45),
            "mileage_km": 5000.0,
            "fuel_level_pct": 80.0,
        }
        res = calculate_vehicle_telemetry(v, now=NOW)
        assert res["days_since_service"] == 45
        assert res["is_over_days"] is False
        assert res["is_over_mileage"] is False
        assert res["is_low_fuel"] is False

    def test_over_mileage_threshold(self):
        v = {
            "registration": "TEST-02",
            "last_maintenance": NOW - timedelta(days=10),
            "mileage_km": 10500.0,
            "fuel_level_pct": 90.0,
        }
        res = calculate_vehicle_telemetry(v, now=NOW)
        assert res["is_over_mileage"] is True
        assert res["needs_maintenance"] is True

    def test_over_days_threshold(self):
        v = {
            "registration": "TEST-03",
            "last_maintenance": NOW - timedelta(days=95),
            "mileage_km": 2000.0,
            "fuel_level_pct": 50.0,
        }
        res = calculate_vehicle_telemetry(v, now=NOW)
        assert res["days_since_service"] == 95
        assert res["is_over_days"] is True
        assert res["needs_maintenance"] is True

    def test_low_fuel_threshold(self):
        v = {
            "registration": "TEST-04",
            "last_maintenance": NOW - timedelta(days=10),
            "mileage_km": 1000.0,
            "fuel_level_pct": 12.0,
        }
        res = calculate_vehicle_telemetry(v, now=NOW)
        assert res["is_low_fuel"] is True
        assert res["needs_maintenance"] is True


# =============================================================
#  Test 2: Threshold Flagging Logic & Utilization %
# =============================================================

class TestThresholdFlagging:
    """Unit tests for flag_maintenance_thresholds."""

    def test_flagging_and_utilization(self):
        raw_vehicles = _serialise_rows(SAMPLE_VEHICLES)
        flagged, util_pct, available = flag_maintenance_thresholds(raw_vehicles, now=NOW)

        # 1 in_transit out of 4 -> 25.0%
        assert util_pct == 25.0

        # Flagged should be Vehicle 2 (mileage), Vehicle 3 (days), Vehicle 4 (low fuel)
        flagged_ids = [v["vehicle_id"] for v in flagged]
        assert 2 in flagged_ids
        assert 3 in flagged_ids
        assert 4 in flagged_ids

        # Available should only be Vehicle 1
        assert len(available) == 1
        assert available[0]["vehicle_id"] == 1

    def test_healthy_fleet_no_flagged(self):
        healthy_vehicles = [
            {
                "vehicle_id": 10,
                "registration": "OK-01",
                "vehicle_status": "in_transit",
                "mileage_km": 1000.0,
                "last_maintenance": NOW - timedelta(days=10),
                "fuel_level_pct": 90.0,
            }
        ]
        flagged, util_pct, available = flag_maintenance_thresholds(healthy_vehicles, now=NOW)

        assert len(flagged) == 0
        assert util_pct == 100.0
        assert len(available) == 1

    def test_empty_fleet(self):
        flagged, util_pct, available = flag_maintenance_thresholds([], now=NOW)
        assert flagged == []
        assert util_pct == 0.0
        assert available == []


# =============================================================
#  Test 3: Full Agent -- Happy Path with LLM Plan
# =============================================================

@pytest.mark.asyncio
@patch("agents.fleet_agent.execute_command", new_callable=AsyncMock)
@patch("agents.fleet_agent.execute_query", new_callable=AsyncMock)
async def test_happy_path_with_llm(mock_query, mock_log_cmd):
    """Full integration: DB -> telemetry analysis -> LLM maintenance plan."""
    mock_query.return_value = SAMPLE_VEHICLES
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_FLEET_PLAN)

    result = await fleet_management_agent(EMPTY_STATE, llm_service=mock_llm)

    mock_llm.generate.assert_called_once()

    assert "fleet" in result
    fleet_state = result["fleet"]
    assert fleet_state["vehicle_id"] == 1
    assert fleet_state["registration"] == "MH-04-AB-1234"
    assert fleet_state["status"] == "available"
    assert fleet_state["_fleet_utilization_pct"] == 25.0
    assert len(fleet_state["maintenance_alerts"]) == 3

    # Check alert structure
    alert0 = fleet_state["maintenance_alerts"][0]
    assert alert0["vehicle_id"] == 2
    assert alert0["severity"] == "critical"
    assert alert0["action_category"] == "Immediate Grounding"

    assert "error" not in result


# =============================================================
#  Test 4: LLM Failure -> Deterministic Grounding Fallback
# =============================================================

@pytest.mark.asyncio
@patch("agents.fleet_agent.execute_command", new_callable=AsyncMock)
@patch("agents.fleet_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_fallback(mock_query, mock_log_cmd):
    """When LLM fails, strict rule-based fallback grounds critical vehicles."""
    mock_query.return_value = SAMPLE_VEHICLES
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM Provider unreachable"))

    result = await fleet_management_agent(EMPTY_STATE, llm_service=mock_llm)

    assert "error" not in result
    fleet_state = result["fleet"]

    alerts = fleet_state["maintenance_alerts"]
    assert len(alerts) == 3

    # Vehicle 2 (12,500 km) and Vehicle 3 (100 days) must be Immediate Grounding
    g_alerts = [a for a in alerts if a["action_category"] == "Immediate Grounding"]
    assert len(g_alerts) == 2
    g_ids = [a["vehicle_id"] for a in g_alerts]
    assert 2 in g_ids
    assert 3 in g_ids


# =============================================================
#  Test 5: Empty Vehicles List
# =============================================================

@pytest.mark.asyncio
@patch("agents.fleet_agent.execute_command", new_callable=AsyncMock)
@patch("agents.fleet_agent.execute_query", new_callable=AsyncMock)
async def test_empty_vehicles(mock_query, mock_log_cmd):
    """When no vehicles exist in DB, return empty fleet state."""
    mock_query.return_value = []
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()

    result = await fleet_management_agent(EMPTY_STATE, llm_service=mock_llm)

    mock_llm.generate.assert_called_once()
    assert result["fleet"]["available_vehicles"] == []
    assert result["fleet"]["maintenance_alerts"] == []
    assert "error" not in result


# =============================================================
#  Test 6: DB Failure Propagation
# =============================================================

@pytest.mark.asyncio
@patch("agents.fleet_agent.execute_command", new_callable=AsyncMock)
@patch("agents.fleet_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error(mock_query, mock_log_cmd):
    """DB query failure propagates error in state."""
    mock_query.side_effect = ConnectionError("PostgreSQL connection timeout")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await fleet_management_agent(EMPTY_STATE)

    assert "error" in result
    assert "PostgreSQL connection timeout" in result["error"]
    assert result["fleet"]["available_vehicles"] == []
    assert result["fleet"]["maintenance_alerts"] == []


# =============================================================
#  Test 7: State Key Validation
# =============================================================

@pytest.mark.asyncio
@patch("agents.fleet_agent.execute_command", new_callable=AsyncMock)
@patch("agents.fleet_agent.execute_query", new_callable=AsyncMock)
async def test_state_keys_match_global_state(mock_query, mock_log_cmd):
    """Returned keys must match GlobalLogisticsState."""
    mock_query.return_value = SAMPLE_VEHICLES
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_FLEET_PLAN)

    result = await fleet_management_agent(EMPTY_STATE, llm_service=mock_llm)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected top-level key '{key}'"

    fleet_state = result["fleet"]
    required_keys = {
        "vehicle_id", "registration", "status",
        "current_lat", "current_lon", "fuel_level_pct",
        "available_vehicles", "maintenance_alerts",
    }
    assert required_keys.issubset(fleet_state.keys()), f"Missing keys: {required_keys - fleet_state.keys()}"


# =============================================================
#  Test 8: Fallback Fleet Plan Generator
# =============================================================

class TestFallbackFleetPlan:
    """Verify fallback fleet plan categorisation."""

    def test_strict_grounding_rule(self):
        flagged = [
            {"vehicle_id": 10, "registration": "TRK-99", "mileage_km": 11000.0, "days_since_service": 50, "fuel_level_pct": 80.0},
            {"vehicle_id": 11, "registration": "VAN-88", "mileage_km": 2000.0, "days_since_service": 100, "fuel_level_pct": 50.0},
            {"vehicle_id": 12, "registration": "VAN-77", "mileage_km": 3000.0, "days_since_service": 20, "fuel_level_pct": 10.0},
        ]
        res = build_fallback_fleet_plan(flagged, utilization_pct=50.0)

        plan = res["maintenance_plan"]["categorized_vehicles"]
        assert len(plan) == 3
        assert plan[0]["action_category"] == "Immediate Grounding"  # > 10,000 km
        assert plan[1]["action_category"] == "Immediate Grounding"  # > 90 days
        assert plan[2]["action_category"] == "Safe for Local Routes Only"  # low fuel
