"""
Agent 5: Fleet Management Agent

Responsibilities:
  - Query vehicle fleet telemetry from PostgreSQL
  - Calculate days since last maintenance and mileage accumulated
  - Flag vehicles exceeding critical threshold (> 10,000 km or > 90 days or low fuel)
  - Compute overall fleet utilisation rate (% of active/in_transit vehicles)
  - Invoke LLM for predictive maintenance & vehicle reallocation recommendations
    (categorising into "Immediate Grounding", "Schedule End-of-Week", "Safe for Local Routes Only")
  - Fall back to strict rule-based grounding if LLM call fails
  - Log execution audit to agent_task_log

Node interface (LangGraph-ready):
  Input:  dict  -- GlobalLogisticsState (or its fleet sub-state)
  Output: dict  -- partial state update with { "fleet": FleetState }
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from db.connection import execute_query, execute_command
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# -- Constants ------------------------------------------------

CRITICAL_MILEAGE_KM = 10000.0    # Mileage limit before required service
CRITICAL_DAYS_LIMIT = 90         # Days limit before required service
LOW_FUEL_THRESHOLD_PCT = 15.0    # Fuel percentage triggering alert

# -- SQL Queries ----------------------------------------------

ALL_VEHICLES_QUERY = """
    SELECT
        v.id              AS vehicle_id,
        v.registration,
        v.type            AS vehicle_type,
        v.status          AS vehicle_status,
        v.capacity_kg,
        v.capacity_m3,
        v.current_lat,
        v.current_lon,
        v.home_warehouse  AS warehouse_id,
        v.fuel_level_pct,
        v.mileage_km,
        v.last_maintenance,
        v.next_maintenance,
        v.is_active,
        w.code            AS warehouse_code,
        w.name            AS warehouse_name
    FROM vehicles v
    LEFT JOIN warehouses w ON w.id = v.home_warehouse
    WHERE v.is_active = TRUE
    ORDER BY v.id ASC
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""


# =============================================================
#  Telemetry Calculations & Threshold Flagging
# =============================================================

def calculate_vehicle_telemetry(
    vehicle: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Calculate telemetry metrics for a single vehicle:
      - days_since_service: Days elapsed since `last_maintenance`
      - mileage_km: Current mileage
      - is_over_mileage: True if mileage_km >= CRITICAL_MILEAGE_KM
      - is_over_days: True if days_since_service >= CRITICAL_DAYS_LIMIT
      - is_low_fuel: True if fuel_level_pct <= LOW_FUEL_THRESHOLD_PCT

    Args:
        vehicle: Dict containing vehicle attributes from DB.
        now: Reference datetime (defaults to current UTC time).

    Returns:
        Dict annotated with calculated telemetry fields.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    last_maint = vehicle.get("last_maintenance")
    if last_maint is not None:
        if isinstance(last_maint, str):
            try:
                last_maint_dt = datetime.fromisoformat(last_maint)
            except ValueError:
                last_maint_dt = now
        elif isinstance(last_maint, datetime):
            last_maint_dt = last_maint
        else:
            last_maint_dt = now

        # Ensure timezone-aware comparison
        if last_maint_dt.tzinfo is None:
            last_maint_dt = last_maint_dt.replace(tzinfo=timezone.utc)

        days_since_service = max(0, (now - last_maint_dt).days)
    else:
        # Default if last_maintenance is unknown/None
        days_since_service = 999

    mileage = float(vehicle.get("mileage_km", 0.0) or 0.0)
    fuel = float(vehicle.get("fuel_level_pct", 100.0) or 100.0)

    is_over_mileage = mileage >= CRITICAL_MILEAGE_KM
    is_over_days = days_since_service >= CRITICAL_DAYS_LIMIT
    is_low_fuel = fuel <= LOW_FUEL_THRESHOLD_PCT

    needs_maintenance = is_over_mileage or is_over_days or is_low_fuel

    telemetry = dict(vehicle)
    telemetry.update({
        "days_since_service": days_since_service,
        "mileage_km": mileage,
        "fuel_level_pct": fuel,
        "is_over_mileage": is_over_mileage,
        "is_over_days": is_over_days,
        "is_low_fuel": is_low_fuel,
        "needs_maintenance": needs_maintenance,
    })

    return telemetry


def flag_maintenance_thresholds(
    vehicles: list[dict[str, Any]],
    now: datetime | None = None,
    mileage_limit: float = CRITICAL_MILEAGE_KM,
    days_limit: int = CRITICAL_DAYS_LIMIT,
) -> tuple[list[dict[str, Any]], float, list[dict[str, Any]]]:
    """
    Process fleet vehicles, compute utilization %, and flag vehicles requiring action.

    Args:
        vehicles: Raw list of vehicle dicts from DB.
        now: Reference datetime.
        mileage_limit: Critical mileage threshold.
        days_limit: Critical days threshold.

    Returns:
        Tuple of:
          - Flagged vehicles list (exceeding thresholds)
          - Overall fleet utilization percentage (active/in_transit vs total)
          - Available (healthy & available) vehicles list
    """
    if not vehicles:
        return [], 0.0, []

    telemetry_list = [calculate_vehicle_telemetry(v, now=now) for v in vehicles]

    total_count = len(telemetry_list)
    in_transit_count = sum(
        1 for v in telemetry_list if v.get("vehicle_status") == "in_transit"
    )
    available_count = sum(
        1 for v in telemetry_list
        if v.get("vehicle_status") == "available" and not v.get("needs_maintenance")
    )

    # Utilization % = in_transit / total_vehicles * 100
    utilization_pct = round((in_transit_count / total_count) * 100.0, 2)

    flagged_vehicles = []
    available_vehicles = []

    for v in telemetry_list:
        status = v.get("vehicle_status", "available")
        days = v["days_since_service"]
        mileage = v["mileage_km"]
        fuel = v["fuel_level_pct"]

        if mileage >= mileage_limit or days >= days_limit or fuel <= LOW_FUEL_THRESHOLD_PCT or status in ("maintenance", "out_of_service"):
            flagged_vehicles.append(v)
        else:
            available_vehicles.append(v)

    return flagged_vehicles, utilization_pct, available_vehicles


# =============================================================
#  LLM Integration & Fallback Plan
# =============================================================

SYSTEM_INSTRUCTION = """You are a Senior Fleet Manager and Logistics Maintenance Specialist.
Analyse vehicle telemetry, mileage, service history, and fleet utilization.
Categorise flagged vehicles into precise operational action categories:
- "Immediate Grounding" (critical safety or major limit exceedance)
- "Schedule End-of-Week" (nearing limit, non-critical)
- "Safe for Local Routes Only" (minor anomaly, e.g. low fuel or near local warehouse)
Always respond with valid JSON matching the exact schema provided."""

FLEET_MAINTENANCE_PROMPT_TEMPLATE = """Analyse the following flagged vehicle telemetry and fleet status to generate a Fleet Maintenance & Reallocation Plan.

## Overall Fleet Utilization Rate
{utilization_pct}% of total fleet currently in transit.

## Flagged Vehicles Telemetry
{flagged_json}

## Current Date
{current_date}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "maintenance_plan": {{
    "categorized_vehicles": [
      {{
        "vehicle_id": <int>,
        "registration": "<string>",
        "action_category": "<Immediate Grounding|Schedule End-of-Week|Safe for Local Routes Only>",
        "reallocation_note": "<specific directive or alternative vehicle assignment>",
        "justification": "<detailed operational reason based on telemetry>"
      }}
    ],
    "fleet_health_summary": "<one-sentence summary of fleet readiness>",
    "recommendations": [
      "<string: actionable fleet management advice>"
    ]
  }},
  "summary": "<one-paragraph executive summary of the fleet maintenance decision>"
}}

Rules:
- Ground any vehicle with mileage >= 10,000 km AND days >= 90 immediately.
- Vehicles with low fuel (<15%) should be sent for refuelling before deployment.
- Reallocate loads to available healthy vehicles if a truck is grounded.
"""


def build_fallback_fleet_plan(
    flagged_vehicles: list[dict[str, Any]],
    utilization_pct: float,
) -> dict[str, Any]:
    """
    Deterministic fallback when LLM is unavailable:
    Enforces strict rule-based vehicle grounding.
    """
    categorized = []
    recommendations = []

    for v in flagged_vehicles:
        mileage = v.get("mileage_km", 0.0)
        days = v.get("days_since_service", 0)
        fuel = v.get("fuel_level_pct", 100.0)
        reg = v.get("registration", "UNKNOWN")
        vid = v.get("vehicle_id", 0)

        # Strict rules:
        if mileage >= CRITICAL_MILEAGE_KM or days >= CRITICAL_DAYS_LIMIT:
            cat = "Immediate Grounding"
            note = "Vehicle grounded by strict threshold rule. Send to maintenance bay."
            justification = f"Exceeded safety thresholds: {mileage:.1f} km / {days} days since service."
        elif fuel <= LOW_FUEL_THRESHOLD_PCT:
            cat = "Safe for Local Routes Only"
            note = "Fuel level critical. Refuel immediately at nearest hub."
            justification = f"Fuel level at {fuel:.1f}% (below {LOW_FUEL_THRESHOLD_PCT}% limit)."
        else:
            cat = "Schedule End-of-Week"
            note = "Schedule routine preventive maintenance check."
            justification = f"Vehicle flagged due to status '{v.get('vehicle_status')}'. Nearing maintenance interval."

        categorized.append({
            "vehicle_id": vid,
            "registration": reg,
            "action_category": cat,
            "reallocation_note": note,
            "justification": justification,
        })

    if flagged_vehicles:
        recommendations.append(f"{len(categorized)} vehicle(s) flagged for maintenance review.")
    else:
        recommendations.append("Fleet is operating within healthy telemetry bounds.")

    return {
        "maintenance_plan": {
            "categorized_vehicles": categorized,
            "fleet_health_summary": f"Fleet utilization is {utilization_pct}%. {len(categorized)} vehicle(s) require action.",
            "recommendations": recommendations,
        },
        "summary": f"Deterministic fleet maintenance plan generated. {len(categorized)} vehicle(s) evaluated under strict rules.",
    }


# =============================================================
#  Core Agent Function
# =============================================================

async def fleet_management_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Fleet Management Agent -- LangGraph node function.

    Pipeline:
      1. Query vehicles telemetry from database via asyncpg.
      2. Compute days since service, accumulated mileage, and low fuel indicators.
      3. Calculate overall fleet utilization rate (% in_transit).
      4. Programmatically flag vehicles exceeding critical thresholds.
      5. Invoke LLM for predictive maintenance & reallocation plan (with fallback).
      6. Log task execution to agent_task_log.
      7. Return partial state update for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict.
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated ``fleet`` sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None

    try:
        # -- Step 1: Query vehicles data ----------------------
        vehicle_rows = await execute_query(ALL_VEHICLES_QUERY)
        vehicles_serialised = _serialise_rows(vehicle_rows)
        logger.info("Retrieved telemetry for %d vehicle(s)", len(vehicles_serialised))

        # -- Step 2: Telemetry analysis & threshold flagging --
        now = datetime.now(timezone.utc)
        flagged_vehicles, utilization_pct, available_vehicles = flag_maintenance_thresholds(
            vehicles_serialised, now=now
        )
        logger.info("Fleet utilization: %.2f%% | Flagged: %d | Available: %d",
                    utilization_pct, len(flagged_vehicles), len(available_vehicles))

        # -- Step 3: Select primary vehicle for state representation
        primary = vehicles_serialised[0] if vehicles_serialised else {
            "vehicle_id": 1,
            "registration": "UNKNOWN",
            "vehicle_status": "available",
            "current_lat": 19.0760,
            "current_lon": 72.8777,
            "fuel_level_pct": 100.0,
        }

        # -- Step 4: LLM Predictive Maintenance Plan ---------
        maintenance_result: dict[str, Any]

        if llm_service is None:
            llm_service = LLMService()

        try:
            prompt = FLEET_MAINTENANCE_PROMPT_TEMPLATE.format(
                utilization_pct=utilization_pct,
                flagged_json=json.dumps(flagged_vehicles, indent=2) if flagged_vehicles
                    else "None -- all fleet vehicles operate within normal parameters.",
                current_date=now.strftime("%Y-%m-%d %H:%M UTC"),
            )
            maintenance_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=4096,
            )
            logger.info("LLM fleet maintenance plan generated successfully")
        except Exception as exc:
            logger.error("LLM fleet management call failed, using deterministic fallback: %s", exc)
            maintenance_result = build_fallback_fleet_plan(flagged_vehicles, utilization_pct)

        # -- Step 5: Format maintenance alerts for state ------
        maint_plan = maintenance_result.get("maintenance_plan", {})
        categorized_list = maint_plan.get("categorized_vehicles", [])

        maintenance_alerts = []
        for cat in categorized_list:
            maintenance_alerts.append({
                "vehicle_id": cat.get("vehicle_id"),
                "registration": cat.get("registration"),
                "severity": "critical" if cat.get("action_category") == "Immediate Grounding" else "warning",
                "action_category": cat.get("action_category"),
                "reallocation_note": cat.get("reallocation_note"),
                "justification": cat.get("justification"),
            })

        # -- Step 6: Assemble state update --------------------
        result: dict[str, Any] = {
            "fleet": {
                "vehicle_id": primary["vehicle_id"],
                "registration": primary["registration"],
                "status": primary.get("vehicle_status", "available"),
                "current_lat": float(primary.get("current_lat") or 19.0760),
                "current_lon": float(primary.get("current_lon") or 72.8777),
                "fuel_level_pct": float(primary.get("fuel_level_pct") or 100.0),
                "available_vehicles": available_vehicles,
                "maintenance_alerts": maintenance_alerts,
                # Extended metadata
                "_fleet_utilization_pct": utilization_pct,
                "_flagged_vehicles": flagged_vehicles,
                "_maintenance_plan": maintenance_result,
            },
        }
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Fleet Management Agent failed: %s", exc)
        return {
            "fleet": {
                "vehicle_id": 0,
                "registration": "UNKNOWN",
                "status": "out_of_service",
                "current_lat": 0.0,
                "current_lon": 0.0,
                "fuel_level_pct": 0.0,
                "available_vehicles": [],
                "maintenance_alerts": [],
            },
            "error": f"Fleet Management Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        try:
            input_payload = json.dumps({
                "query": state.get("query", ""),
                "intent": state.get("intent", ""),
            })
            output_summary = json.dumps({
                "vehicles_count": len(vehicles_serialised) if "vehicles_serialised" in locals() else 0,
                "flagged_count": len(flagged_vehicles) if "flagged_vehicles" in locals() else 0,
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "fleet_management",
                "fleet_maintenance_check",
                input_payload,
                output_summary,
                task_status,
                elapsed_ms,
            )
        except Exception as log_exc:
            logger.warning("Failed to log agent task: %s", log_exc)


# =============================================================
#  Helpers
# =============================================================

def _serialise_rows(rows: list[dict]) -> list[dict]:
    """
    Convert asyncpg Row dicts to JSON-safe dicts.
    Handles Decimal -> float, date/datetime -> ISO string.
    """
    import decimal
    from datetime import date as date_type

    clean = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            if isinstance(value, decimal.Decimal):
                cleaned_row[key] = float(value)
            elif isinstance(value, datetime):
                cleaned_row[key] = value.isoformat()
            elif isinstance(value, date_type):
                cleaned_row[key] = value.isoformat()
            else:
                cleaned_row[key] = value
        clean.append(cleaned_row)
    return clean
