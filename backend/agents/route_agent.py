"""
Agent 4: Route Optimization Agent

Responsibilities:
  - Query unassigned shipments/orders and available vehicles & warehouses
  - Compute initial delivery sequence using Nearest Neighbor (Greedy TSP) algorithm
  - Calculate exact Haversine distances between warehouse and delivery stops
  - Invoke LLM (acting as Senior Dispatcher) to adjust route for environmental constraints
    (traffic congestion, severe weather, urgent SLA deadlines)
  - Fall back to pure Nearest Neighbor algorithmic route if LLM fails or times out
  - Log task execution to agent_task_log

Node interface (LangGraph-ready):
  Input:  dict  -- GlobalLogisticsState (or its route sub-state)
  Output: dict  -- partial state update with { "route": RouteState }
"""

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

from db.connection import execute_query, execute_command
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# -- Constants ------------------------------------------------

EARTH_RADIUS_KM = 6371.0
AVERAGE_SPEED_KMH = 40.0       # Average urban logistics travel speed
STOP_SERVICE_TIME_MIN = 15     # Fixed service time per delivery stop

# -- SQL Queries ----------------------------------------------

DELIVERY_STOPS_QUERY = """
    SELECT
        o.id              AS order_id,
        o.order_number,
        o.customer_name,
        o.delivery_address,
        o.delivery_city,
        COALESCE(o.delivery_lat, 19.0760) AS latitude,
        COALESCE(o.delivery_lon, 72.8777) AS longitude,
        o.priority        AS order_priority,
        o.status          AS order_status,
        o.promised_at
    FROM orders o
    WHERE o.status IN ('pending', 'confirmed', 'picking')
    ORDER BY o.priority DESC, o.promised_at ASC NULLS LAST, o.id
"""

AVAILABLE_VEHICLES_QUERY = """
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
        w.code            AS warehouse_code,
        w.name            AS warehouse_name,
        w.latitude        AS warehouse_lat,
        w.longitude       AS warehouse_lon
    FROM vehicles v
    LEFT JOIN warehouses w ON w.id = v.home_warehouse
    WHERE v.is_active = TRUE AND v.status IN ('available', 'in_transit')
    ORDER BY v.status ASC, v.id ASC
"""

ORIGIN_WAREHOUSE_QUERY = """
    SELECT
        w.id              AS warehouse_id,
        w.code            AS warehouse_code,
        w.name            AS warehouse_name,
        COALESCE(w.latitude, 19.0760) AS latitude,
        COALESCE(w.longitude, 72.8777) AS longitude
    FROM warehouses w
    WHERE w.is_active = TRUE
    ORDER BY w.id ASC
    LIMIT 1
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""


# =============================================================
#  Haversine Distance & Route Calculations
# =============================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) using Haversine formula.

    Returns:
        Distance in kilometers rounded to 2 decimal places.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)

    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = EARTH_RADIUS_KM * c
    return round(distance, 2)


def nearest_neighbor_route(
    origin: dict[str, Any],
    stops: list[dict[str, Any]],
    avg_speed_kmh: float = AVERAGE_SPEED_KMH,
    service_time_min: int = STOP_SERVICE_TIME_MIN,
) -> tuple[list[dict[str, Any]], float, int]:
    """
    Greedy Nearest Neighbor Traveling Salesperson Problem (TSP) heuristic.

    Starting from ``origin``, iteratively visits the unvisited stop
    closest in Haversine distance to the current location.

    Args:
        origin: Dict with ``latitude`` and ``longitude``.
        stops: List of stop dicts with ``latitude`` and ``longitude``.
        avg_speed_kmh: Speed for travel duration estimation.
        service_time_min: Fixed service time at each delivery location.

    Returns:
        Tuple of:
          - Ordered list of stop dicts with stop_order, distance, and ETA
          - Total route distance (km)
          - Total route duration (min)
    """
    if not stops:
        return [], 0.0, 0

    unvisited = [dict(s) for s in stops]
    route = []
    current_lat = float(origin.get("latitude", 19.0760))
    current_lon = float(origin.get("longitude", 72.8777))

    total_distance_km = 0.0
    cumulative_duration_min = 0

    stop_order = 1
    while unvisited:
        # Find nearest unvisited stop
        nearest_idx = min(
            range(len(unvisited)),
            key=lambda i: haversine_distance(
                current_lat, current_lon,
                float(unvisited[i]["latitude"]), float(unvisited[i]["longitude"])
            ),
        )

        next_stop = unvisited.pop(nearest_idx)
        stop_lat = float(next_stop["latitude"])
        stop_lon = float(next_stop["longitude"])

        leg_distance = haversine_distance(current_lat, current_lon, stop_lat, stop_lon)
        leg_travel_time_min = int(round((leg_distance / avg_speed_kmh) * 60))

        total_distance_km += leg_distance
        cumulative_duration_min += leg_travel_time_min + service_time_min

        next_stop["stop_order"] = stop_order
        next_stop["leg_distance_km"] = round(leg_distance, 2)
        next_stop["cumulative_distance_km"] = round(total_distance_km, 2)
        next_stop["estimated_arrival_min"] = cumulative_duration_min
        next_stop["stop_type"] = "delivery"

        route.append(next_stop)
        current_lat, current_lon = stop_lat, stop_lon
        stop_order += 1

    return route, round(total_distance_km, 2), cumulative_duration_min


# =============================================================
#  Environmental Context & LLM Integration
# =============================================================

DEFAULT_ENVIRONMENTAL_CONSTRAINTS = [
    {
        "type": "traffic_congestion",
        "location": "Central Corridor / Highway-4",
        "severity": "high",
        "delay_impact_min": 25,
        "description": "Peak hour rush and roadwork near Highway-4 junction causing heavy slowdowns.",
    },
    {
        "type": "weather_hazard",
        "location": "Coastal Belt / Harbor Line",
        "severity": "medium",
        "delay_impact_min": 15,
        "description": "Heavy monsoon downpour reducing visibility and movement speed.",
    },
]

SYSTEM_INSTRUCTION = """You are a Senior Logistics Dispatcher and Route Optimisation Specialist.
Analyse the algorithmic baseline route sequence and live environmental hazards.
Dynamically re-sequence or adjust the route to bypass traffic jams, weather hazards, and satisfy urgent order SLA deadlines.
Always respond with valid JSON matching the exact schema provided."""

DYNAMIC_ROUTE_PROMPT_TEMPLATE = """Analyse the following algorithmic baseline route sequence and live environmental constraints to produce a Dynamic Route Adjustment Plan.

## Origin Warehouse / Starting Location
{origin_json}

## Algorithmic Baseline Sequence (Nearest Neighbor TSP)
{baseline_route_json}

## Live Environmental & Traffic Hazards
{environmental_json}

## Current Time
{current_time}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "route_adjustment_plan": {{
    "optimized_stop_sequence": [
      {{
        "stop_order": <int: 1-based order>,
        "order_id": <int>,
        "order_number": "<string>",
        "customer_name": "<string>",
        "delivery_address": "<string>",
        "reason_for_sequence": "<brief reason for sequence positioning>"
      }}
    ],
    "avoided_hazards": [
      {{
        "hazard_type": "<string>",
        "location": "<string>",
        "action_taken": "<description of re-routing or timing shift>"
      }}
    ],
    "estimated_delay_warnings": [
      "<string: warning message about anticipated delay or SLA risk>"
    ],
    "revised_total_distance_km": <float>,
    "revised_total_duration_min": <int>
  }},
  "summary": "<one-paragraph executive summary of the dispatch adjustments>"
}}

Rules:
- Prioritise high-priority orders and tight promised_at deadlines.
- Avoid or re-sequence stops affected by severe traffic or weather hazards.
- Retain all stops -- do not drop any delivery orders.
"""


def _build_fallback_route_plan(
    baseline_route: list[dict[str, Any]],
    total_distance_km: float,
    total_duration_min: int,
) -> dict[str, Any]:
    """
    Deterministic fallback when LLM is unavailable:
    Return the pure Nearest Neighbor route sequence as the final plan.
    """
    seq = []
    for stop in baseline_route:
        seq.append({
            "stop_order": stop["stop_order"],
            "order_id": stop["order_id"],
            "order_number": stop["order_number"],
            "customer_name": stop.get("customer_name", ""),
            "delivery_address": stop.get("delivery_address", ""),
            "reason_for_sequence": f"Algorithmic Nearest Neighbor (Leg distance: {stop['leg_distance_km']} km).",
        })

    return {
        "route_adjustment_plan": {
            "optimized_stop_sequence": seq,
            "avoided_hazards": [],
            "estimated_delay_warnings": [
                "Using pure algorithmic Nearest Neighbor route sequence (LLM dynamic dispatch unavailable).",
            ],
            "revised_total_distance_km": total_distance_km,
            "revised_total_duration_min": total_duration_min,
        },
        "summary": f"Baseline Nearest Neighbor route with {len(seq)} stop(s) over {total_distance_km} km.",
    }


# =============================================================
#  Core Agent Function
# =============================================================

async def route_optimization_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Route Optimization Agent -- LangGraph node function.

    Pipeline:
      1. Query active delivery orders and available vehicles & origin warehouse.
      2. Compute algorithmic baseline route via Nearest Neighbor (Greedy TSP).
      3. Calculate Haversine distances, leg travel times, and cumulative ETAs.
      4. Pass route + simulated environmental hazards to LLM for dynamic dispatch adjustment.
      5. Fall back to deterministic Nearest Neighbor route if LLM fails.
      6. Log execution to agent_task_log.
      7. Return partial state update for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict.
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated ``route`` sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None

    try:
        # -- Step 1: Query origin warehouse & vehicles --------
        warehouse_rows = await execute_query(ORIGIN_WAREHOUSE_QUERY)
        origin_wh = _serialise_rows(warehouse_rows)[0] if warehouse_rows else {
            "warehouse_id": 1,
            "warehouse_code": "WH-MUM-01",
            "warehouse_name": "Mumbai Central Hub",
            "latitude": 19.0760,
            "longitude": 72.8777,
        }

        vehicle_rows = await execute_query(AVAILABLE_VEHICLES_QUERY)
        vehicles = _serialise_rows(vehicle_rows)
        assigned_vehicle = vehicles[0] if vehicles else {
            "vehicle_id": 1,
            "registration": "MH-04-AB-1234",
            "type": "truck",
            "status": "available",
        }

        # -- Step 2: Query delivery stops ---------------------
        raw_stops = await execute_query(DELIVERY_STOPS_QUERY)
        stops_serialised = _serialise_rows(raw_stops)
        logger.info("Found %d pending delivery stop(s)", len(stops_serialised))

        # -- Step 3: No stops scenario ------------------------
        if not stops_serialised:
            return {
                "route": {
                    "route_id": 0,
                    "vehicle_id": assigned_vehicle["vehicle_id"],
                    "origin_warehouse_id": origin_wh["warehouse_id"],
                    "stops": [],
                    "total_distance_km": 0.0,
                    "total_duration_min": 0,
                    "optimized_order": [],
                },
            }

        # -- Step 4: Nearest Neighbor Algorithmic Baseline ----
        baseline_route, total_dist, total_dur = nearest_neighbor_route(
            origin_wh, stops_serialised
        )
        logger.info("Nearest Neighbor route: %d stop(s), %.2f km, %d min",
                    len(baseline_route), total_dist, total_dur)

        # -- Step 5: Environmental constraints ----------------
        env_constraints = state.get("environmental_constraints") or DEFAULT_ENVIRONMENTAL_CONSTRAINTS

        # -- Step 6: LLM Dynamic Dispatch Adjustment ----------
        adjustment_result: dict[str, Any]

        if llm_service is None:
            llm_service = LLMService()

        try:
            prompt = DYNAMIC_ROUTE_PROMPT_TEMPLATE.format(
                origin_json=json.dumps(origin_wh, indent=2),
                baseline_route_json=json.dumps(baseline_route, indent=2),
                environmental_json=json.dumps(env_constraints, indent=2),
                current_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            adjustment_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.25,
                max_output_tokens=4096,
            )
            logger.info("LLM route adjustment generated successfully")
        except Exception as exc:
            logger.error("LLM route optimization failed, using baseline fallback: %s", exc)
            adjustment_result = _build_fallback_route_plan(baseline_route, total_dist, total_dur)

        # -- Step 7: Assemble state update --------------------
        route_plan = adjustment_result.get("route_adjustment_plan", {})
        seq_items = route_plan.get("optimized_stop_sequence", [])

        # Extract order IDs sequence
        optimized_order_ids = [item["order_id"] for item in seq_items if "order_id" in item]
        if not optimized_order_ids:
            optimized_order_ids = [s["order_id"] for s in baseline_route]

        revised_dist = float(route_plan.get("revised_total_distance_km", total_dist))
        revised_dur = int(route_plan.get("revised_total_duration_min", total_dur))

        # Re-map full stop details to match optimized sequence
        baseline_by_id = {s["order_id"]: s for s in baseline_route}
        final_stops = []
        for idx, item in enumerate(seq_items, start=1):
            oid = item.get("order_id")
            if oid in baseline_by_id:
                stop_data = dict(baseline_by_id[oid])
                stop_data["stop_order"] = idx
                stop_data["reason_for_sequence"] = item.get("reason_for_sequence", "")
                final_stops.append(stop_data)
            else:
                final_stops.append(item)

        result: dict[str, Any] = {
            "route": {
                "route_id": 1,
                "vehicle_id": assigned_vehicle["vehicle_id"],
                "origin_warehouse_id": origin_wh["warehouse_id"],
                "stops": final_stops if final_stops else baseline_route,
                "total_distance_km": revised_dist,
                "total_duration_min": revised_dur,
                "optimized_order": optimized_order_ids,
                # Extended metadata
                "_vehicle_info": assigned_vehicle,
                "_origin_warehouse": origin_wh,
                "_environmental_constraints": env_constraints,
                "_adjustment_plan": adjustment_result,
            },
        }
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Route Optimization Agent failed: %s", exc)
        return {
            "route": {
                "route_id": 0,
                "vehicle_id": 0,
                "origin_warehouse_id": 0,
                "stops": [],
                "total_distance_km": 0.0,
                "total_duration_min": 0,
                "optimized_order": [],
            },
            "error": f"Route Optimization Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        try:
            input_payload = json.dumps({
                "query": state.get("query", ""),
                "intent": state.get("intent", ""),
            })
            output_summary = json.dumps({
                "stops_count": len(stops_serialised) if "stops_serialised" in locals() else 0,
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "route_optimization",
                "route_optimization",
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
