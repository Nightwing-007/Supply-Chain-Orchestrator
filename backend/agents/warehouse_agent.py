"""
Agent 2: Warehouse Operations Agent

Responsibilities:
  - Monitor warehouse capacity utilisation (flag > 85 %)
  - Compute item turnover frequencies from inventory transactions
  - Algorithmic bin allocation using cycle-sort by turnover (hot items near dispatch)
  - Generate prioritised pick lists for active orders
  - Invoke LLM for a structured Warehouse Optimization Plan
  - Deterministic fallback if LLM is unavailable

Node interface (LangGraph-ready):
  Input:  dict  — GlobalLogisticsState (or its warehouse sub-state)
  Output: dict  — partial state update with { "warehouse": WarehouseState }
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from db.connection import execute_query, execute_command
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

CAPACITY_THRESHOLD_PCT = 85.0  # Warehouses above this % are flagged

# ── SQL Queries ──────────────────────────────────────────────

WAREHOUSE_CAPACITY_QUERY = """
    SELECT
        w.id              AS warehouse_id,
        w.code            AS warehouse_code,
        w.name            AS warehouse_name,
        w.city,
        w.total_capacity,
        w.used_capacity,
        CASE
            WHEN w.total_capacity > 0
            THEN ROUND((w.used_capacity::numeric / w.total_capacity) * 100, 2)
            ELSE 0
        END AS utilization_pct
    FROM warehouses w
    WHERE w.is_active = TRUE
    ORDER BY utilization_pct DESC
"""

ITEM_TURNOVER_QUERY = """
    SELECT
        i.id              AS inventory_id,
        i.warehouse_id,
        w.code            AS warehouse_code,
        i.product_id,
        p.sku,
        p.name            AS product_name,
        p.unit_volume_m3,
        i.quantity_on_hand,
        COALESCE(txn.pick_count, 0)  AS pick_count,
        COALESCE(txn.total_picked, 0) AS total_picked
    FROM inventory i
    JOIN products   p ON p.id = i.product_id
    JOIN warehouses w ON w.id = i.warehouse_id
    LEFT JOIN (
        SELECT
            inventory_id,
            COUNT(*)       AS pick_count,
            SUM(ABS(quantity)) AS total_picked
        FROM inventory_transactions
        WHERE txn_type = 'pick'
        GROUP BY inventory_id
    ) txn ON txn.inventory_id = i.id
    WHERE p.is_active = TRUE AND w.is_active = TRUE
    ORDER BY w.code, COALESCE(txn.pick_count, 0) DESC
"""

PENDING_PICKS_QUERY = """
    SELECT
        o.id              AS order_id,
        o.order_number,
        o.priority        AS order_priority,
        o.promised_at,
        oi.product_id,
        p.sku,
        p.name            AS product_name,
        oi.quantity,
        oi.fulfilled_from AS warehouse_id,
        w.code            AS warehouse_code
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    JOIN products   p  ON p.id  = oi.product_id
    LEFT JOIN warehouses w ON w.id = oi.fulfilled_from
    WHERE o.status IN ('confirmed', 'picking')
    ORDER BY o.priority DESC, o.promised_at ASC NULLS LAST, o.id
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""


# ═══════════════════════════════════════════════════════════════
#  Algorithmic Bin Allocation — Cycle Sort by Turnover
# ═══════════════════════════════════════════════════════════════

def cycle_sort_bins(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    In-place cycle sort of warehouse bin assignments based on item
    turnover frequency (pick_count).  Higher-turnover items get lower
    bin indices (closer to dispatch area).

    Cycle sort is chosen because:
      • O(n²) worst-case but minimal *writes* — optimal when physical
        bin moves are expensive (each write = a forklift relocation).
      • Guarantees the fewest possible item relocations to reach
        the sorted order.

    Each item dict is annotated with:
      - ``bin_index``    : optimised 1-based bin position
      - ``needs_move``   : True if item must be physically relocated
      - ``old_bin_index``: previous position (if moved)

    Args:
        items: list of dicts, each containing at least ``pick_count``.
               **Mutated in-place** and returned.

    Returns:
        The same list, sorted by descending pick_count and annotated.
    """
    n = len(items)
    if n <= 1:
        for idx, item in enumerate(items):
            item["bin_index"] = idx + 1
            item["needs_move"] = False
        return items

    # Assign original bin indices (1-based, current order)
    for idx, item in enumerate(items):
        item["_original_idx"] = idx

    # ── Cycle sort descending by pick_count ──────────────────
    writes = 0
    for cycle_start in range(n - 1):
        item = items[cycle_start]

        # Find the correct position for this item
        pos = cycle_start
        for i in range(cycle_start + 1, n):
            if items[i]["pick_count"] > item["pick_count"]:
                pos += 1

        # Already in correct position
        if pos == cycle_start:
            continue

        # Skip duplicates
        while pos < n and items[pos]["pick_count"] == item["pick_count"]:
            pos += 1

        # Put item in its correct position
        if pos != cycle_start:
            items[pos], item = item, items[pos]
            writes += 1

        # Rotate the rest of the cycle
        while pos != cycle_start:
            pos = cycle_start
            for i in range(cycle_start + 1, n):
                if items[i]["pick_count"] > item["pick_count"]:
                    pos += 1

            while pos < n and items[pos]["pick_count"] == item["pick_count"]:
                pos += 1

            if item != items[pos]:
                items[pos], item = item, items[pos]
                writes += 1

    # ── Annotate with new bin indices ────────────────────────
    for new_idx, item in enumerate(items):
        old_idx = item.pop("_original_idx")
        item["bin_index"] = new_idx + 1
        item["needs_move"] = (new_idx != old_idx)
        if item["needs_move"]:
            item["old_bin_index"] = old_idx + 1

    logger.info("Cycle sort completed: %d write(s) across %d items", writes, n)
    return items


# ═══════════════════════════════════════════════════════════════
#  Pick List Optimisation
# ═══════════════════════════════════════════════════════════════

def build_optimised_pick_list(
    pending_picks: list[dict[str, Any]],
    bin_map: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    """
    Build a prioritised pick sequence sorted by:
      1. Order priority (descending — higher = more urgent)
      2. SLA deadline (ascending — earlier = more urgent)
      3. Bin index (ascending — closer bins first for efficiency)

    Args:
        pending_picks: raw rows from PENDING_PICKS_QUERY.
        bin_map: mapping of (warehouse_code, sku) → bin_index from cycle sort.

    Returns:
        Sorted list of pick instructions with bin locations.
    """
    picks = []
    for row in pending_picks:
        wh_code = row.get("warehouse_code", "")
        sku = row.get("sku", "")
        bin_index = bin_map.get((wh_code, sku), 9999)  # unknown bins go last
        picks.append({
            "order_id": row["order_id"],
            "order_number": row["order_number"],
            "order_priority": row.get("order_priority", 0),
            "promised_at": _safe_iso(row.get("promised_at")),
            "warehouse_code": wh_code,
            "sku": sku,
            "product_name": row.get("product_name", ""),
            "quantity": row.get("quantity", 0),
            "bin_index": bin_index,
        })

    # Sort: priority DESC → promised_at ASC → bin_index ASC
    picks.sort(key=lambda p: (
        -p["order_priority"],
        p["promised_at"] or "9999-12-31",
        p["bin_index"],
    ))

    # Add pick_sequence number
    for seq, pick in enumerate(picks, start=1):
        pick["pick_sequence"] = seq

    return picks


# ═══════════════════════════════════════════════════════════════
#  Capacity Monitoring
# ═══════════════════════════════════════════════════════════════

def detect_capacity_bottlenecks(
    warehouses: list[dict[str, Any]],
    threshold_pct: float = CAPACITY_THRESHOLD_PCT,
) -> list[dict[str, Any]]:
    """
    Identify warehouses exceeding the capacity threshold.

    Returns:
        List of bottleneck dicts with warehouse info and overage details.
    """
    bottlenecks = []
    for wh in warehouses:
        util_pct = float(wh.get("utilization_pct", 0))
        if util_pct > threshold_pct:
            remaining_m3 = wh["total_capacity"] - wh["used_capacity"]
            bottlenecks.append({
                "warehouse_id": wh["warehouse_id"],
                "warehouse_code": wh["warehouse_code"],
                "warehouse_name": wh.get("warehouse_name", ""),
                "city": wh.get("city", ""),
                "total_capacity": wh["total_capacity"],
                "used_capacity": wh["used_capacity"],
                "utilization_pct": util_pct,
                "remaining_m3": remaining_m3,
                "severity": "critical" if util_pct >= 95 else "warning",
            })
    return bottlenecks


# ═══════════════════════════════════════════════════════════════
#  LLM Integration
# ═══════════════════════════════════════════════════════════════

SYSTEM_INSTRUCTION = """You are a warehouse operations expert and industrial engineer.
Analyse warehouse data and provide actionable optimisation recommendations.
Always respond with valid JSON matching the schema provided."""

OPTIMIZATION_PROMPT_TEMPLATE = """Analyse the following warehouse data and generate an Optimization Plan.

## Warehouse Capacity Summary
{capacity_json}

## Capacity Bottlenecks (> {threshold}% utilisation)
{bottleneck_json}

## Bin Allocation (top 20 items by turnover)
{bin_json}

## Current Date
{current_date}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "optimization_plan": {{
    "space_reallocation": [
      {{
        "warehouse_code": "<string>",
        "action": "<string: e.g. 'redistribute to WH-DEL-01', 'archive slow movers'>",
        "estimated_freed_m3": <int>,
        "priority": "<critical|high|medium|low>",
        "rationale": "<brief reason>"
      }}
    ],
    "bottleneck_warnings": [
      {{
        "warehouse_code": "<string>",
        "warning": "<description of the bottleneck>",
        "recommended_action": "<what to do>"
      }}
    ],
    "bin_layout_suggestions": [
      "<string: one-sentence suggestion>"
    ]
  }},
  "summary": "<one-paragraph executive summary>"
}}
"""


def _build_fallback_optimization(
    bottlenecks: list[dict[str, Any]],
    warehouses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic fallback when LLM is unavailable."""
    space_realloc = []
    warnings = []

    for bn in bottlenecks:
        warnings.append({
            "warehouse_code": bn["warehouse_code"],
            "warning": f"Utilisation at {bn['utilization_pct']:.1f}% — only {bn['remaining_m3']} m³ remaining.",
            "recommended_action": "Review slow-moving inventory for archival or redistribution to lower-utilised sites.",
        })
        space_realloc.append({
            "warehouse_code": bn["warehouse_code"],
            "action": "Audit and archive items with zero picks in the last 90 days.",
            "estimated_freed_m3": max(1, int(bn["used_capacity"] * 0.05)),
            "priority": "critical" if bn["severity"] == "critical" else "high",
            "rationale": f"Warehouse is at {bn['utilization_pct']:.1f}% capacity. Freeing 5% would recover "
                         f"~{max(1, int(bn['used_capacity'] * 0.05))} m³.",
        })

    suggestions = [
        "Place high-turnover items within 10m of the dispatch zone.",
        "Group items by category to reduce picker travel distance.",
        "Implement zone-based picking for orders spanning multiple categories.",
    ]

    return {
        "optimization_plan": {
            "space_reallocation": space_realloc,
            "bottleneck_warnings": warnings,
            "bin_layout_suggestions": suggestions,
        },
        "summary": f"{len(bottlenecks)} warehouse(s) exceed the {CAPACITY_THRESHOLD_PCT}% capacity threshold. "
                   f"Immediate review recommended.",
    }


# ═══════════════════════════════════════════════════════════════
#  Core Agent Function
# ═══════════════════════════════════════════════════════════════

async def warehouse_operations_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Warehouse Operations Agent — LangGraph node function.

    1. Queries warehouse capacity and computes utilisation.
    2. Detects capacity bottlenecks (> 85 %).
    3. Computes item turnover and runs cycle-sort bin allocation.
    4. Builds optimised pick lists for active orders.
    5. Calls LLM for a Warehouse Optimization Plan (with fallback).
    6. Logs execution to agent_task_log.
    7. Returns partial state update for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict (or sub-dict).
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated ``warehouse`` sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None
    warehouses_data: list[dict] = []

    try:
        # ── Step 1: Warehouse capacity ───────────────────────
        warehouses_data = await execute_query(WAREHOUSE_CAPACITY_QUERY)
        warehouses_serialised = _serialise_rows(warehouses_data)
        logger.info("Queried %d active warehouse(s)", len(warehouses_serialised))

        # ── Step 2: Bottleneck detection ─────────────────────
        bottlenecks = detect_capacity_bottlenecks(warehouses_serialised)
        logger.info("Detected %d capacity bottleneck(s)", len(bottlenecks))

        # ── Step 3: Item turnover + cycle-sort bin allocation ─
        turnover_rows = await execute_query(ITEM_TURNOVER_QUERY)
        turnover_serialised = _serialise_rows(turnover_rows)

        # Group by warehouse for per-warehouse bin allocation
        wh_groups: dict[str, list[dict]] = {}
        for row in turnover_serialised:
            wh_code = row["warehouse_code"]
            wh_groups.setdefault(wh_code, []).append(row)

        all_bin_allocations: list[dict] = []
        bin_map: dict[tuple[str, str], int] = {}
        for wh_code, items in wh_groups.items():
            sorted_items = cycle_sort_bins(items)
            for item in sorted_items:
                item["warehouse_code"] = wh_code
                bin_map[(wh_code, item["sku"])] = item["bin_index"]
            all_bin_allocations.extend(sorted_items)

        # ── Step 4: Pick list optimisation ───────────────────
        pending_picks_raw = await execute_query(PENDING_PICKS_QUERY)
        pending_picks_serialised = _serialise_rows(pending_picks_raw)
        optimised_picks = build_optimised_pick_list(pending_picks_serialised, bin_map)
        logger.info("Built optimised pick list: %d pick(s)", len(optimised_picks))

        # ── Step 5: LLM optimisation plan ────────────────────
        optimization_result: dict[str, Any]

        if llm_service is None:
            llm_service = LLMService()

        try:
            top_bins = all_bin_allocations[:20]  # send top 20 to LLM
            prompt = OPTIMIZATION_PROMPT_TEMPLATE.format(
                capacity_json=json.dumps(warehouses_serialised, indent=2),
                bottleneck_json=json.dumps(bottlenecks, indent=2) if bottlenecks else "None — all warehouses within limits.",
                threshold=CAPACITY_THRESHOLD_PCT,
                bin_json=json.dumps(top_bins, indent=2),
                current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            optimization_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=4096,
            )
            logger.info("LLM optimization plan generated")
        except Exception as exc:
            logger.error("LLM call failed, using fallback plan: %s", exc)
            optimization_result = _build_fallback_optimization(bottlenecks, warehouses_serialised)

        # ── Step 6: Assemble state update ────────────────────
        opt_plan = optimization_result.get("optimization_plan", {})
        suggestions = (
            opt_plan.get("bin_layout_suggestions", [])
            + [w["warning"] for w in opt_plan.get("bottleneck_warnings", [])]
            + [r["action"] for r in opt_plan.get("space_reallocation", [])]
        )

        result: dict[str, Any] = {
            "warehouse": {
                "utilization_pct": _avg_utilisation(warehouses_serialised),
                "pending_picks": optimised_picks,
                "optimization_suggestions": suggestions,
                # Extended data for downstream agents / UI
                "_capacity_report": warehouses_serialised,
                "_bottlenecks": bottlenecks,
                "_bin_allocations": all_bin_allocations,
                "_optimization_plan": optimization_result,
            },
        }
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Warehouse Operations Agent failed: %s", exc)
        return {
            "warehouse": {
                "utilization_pct": 0.0,
                "pending_picks": [],
                "optimization_suggestions": [],
            },
            "error": f"Warehouse Operations Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        try:
            input_payload = json.dumps({
                "query": state.get("query", ""),
                "intent": state.get("intent", ""),
            })
            output_summary = json.dumps({
                "warehouses_scanned": len(warehouses_data),
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "warehouse_operations",
                "warehouse_ops_check",
                input_payload,
                output_summary,
                task_status,
                elapsed_ms,
            )
        except Exception as log_exc:
            logger.warning("Failed to log agent task: %s", log_exc)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _avg_utilisation(warehouses: list[dict]) -> float:
    """Compute average utilisation across all warehouses."""
    if not warehouses:
        return 0.0
    total = sum(float(w.get("utilization_pct", 0)) for w in warehouses)
    return round(total / len(warehouses), 2)


def _safe_iso(val: Any) -> str | None:
    """Convert a datetime to ISO string, or return the string/None as-is."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _serialise_rows(rows: list[dict]) -> list[dict]:
    """
    Convert asyncpg Row dicts to JSON-safe dicts.
    Handles Decimal → float and datetime → ISO string conversions.
    """
    import decimal

    clean = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            if isinstance(value, decimal.Decimal):
                cleaned_row[key] = float(value)
            elif isinstance(value, datetime):
                cleaned_row[key] = value.isoformat()
            else:
                cleaned_row[key] = value
        clean.append(cleaned_row)
    return clean
