"""
Agent 1: Inventory Planning Agent

Responsibilities:
  - Monitor stock levels across all warehouses
  - Detect low-stock items (quantity_on_hand <= reorder_point)
  - Invoke the LLM to generate a structured Reorder Plan
  - Return state updates compatible with GlobalLogisticsState

Node interface (LangGraph-ready):
  Input:  dict  — GlobalLogisticsState (or its inventory sub-state)
  Output: dict  — partial state update with { "inventory": InventoryState }
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from db.connection import execute_query, execute_command
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ── SQL ──────────────────────────────────────────────────────

LOW_STOCK_QUERY = """
    SELECT
        i.id            AS inventory_id,
        i.warehouse_id,
        w.code          AS warehouse_code,
        w.name          AS warehouse_name,
        i.product_id,
        p.sku,
        p.name          AS product_name,
        p.category,
        p.unit_price,
        i.quantity_on_hand,
        i.quantity_reserved,
        (i.quantity_on_hand - i.quantity_reserved) AS available_qty,
        i.reorder_point,
        i.reorder_qty
    FROM inventory i
    JOIN products  p ON p.id = i.product_id
    JOIN warehouses w ON w.id = i.warehouse_id
    WHERE i.quantity_on_hand <= i.reorder_point
      AND p.is_active = TRUE
      AND w.is_active = TRUE
    ORDER BY (i.reorder_point - i.quantity_on_hand) DESC, p.sku
"""

ALL_STOCK_SUMMARY_QUERY = """
    SELECT
        i.id            AS inventory_id,
        i.warehouse_id,
        w.code          AS warehouse_code,
        i.product_id,
        p.sku,
        p.name          AS product_name,
        i.quantity_on_hand,
        i.quantity_reserved,
        i.reorder_point,
        i.reorder_qty
    FROM inventory i
    JOIN products  p ON p.id = i.product_id
    JOIN warehouses w ON w.id = i.warehouse_id
    WHERE p.is_active = TRUE AND w.is_active = TRUE
    ORDER BY w.code, p.sku
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""

# ── LLM Prompt ───────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are an expert supply chain analyst specializing in Inventory Planning and stock level management.
Your job is to analyse inventory data and generate reorder recommendations.

DOMAIN GUARDRAILS:
Evaluate the user's query. If the query is completely unrelated to your specific domain (Inventory Planning, stock levels, stockout risks, reordering), you MUST NOT process the state data or generate your standard report. Instead, return a polite message stating that this task is outside your scope as the Inventory Planning Agent, leave "reorder_plan" as an empty array [], and explicitly suggest which of the other specific agents (Warehouse Ops, Demand Forecasting, Route Optimization, Fleet Management, Customer Notification) they should select from the dropdown, or suggest switching to the Multi-Agent Supervisor.

Always respond with valid JSON matching the schema provided. Be concise but justify each recommendation when in-domain."""

REORDER_PROMPT_TEMPLATE = """Analyse the following user request and low-stock inventory data to generate a Reorder Plan or evaluate domain relevance.

## User Request / Query
{user_query}

## Low-Stock Items
{low_stock_json}

## Current Date
{current_date}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "reorder_plan": [
    {{
      "inventory_id": <int>,
      "warehouse_code": "<string>",
      "sku": "<string>",
      "product_name": "<string>",
      "current_stock": <int>,
      "reorder_point": <int>,
      "deficit": <int>,
      "recommended_restock_qty": <int>,
      "priority": "<critical|high|medium|low>",
      "justification": "<brief reason>"
    }}
  ],
  "summary": "<executive summary answering the User Request / Query if in-domain, OR a polite out-of-scope redirection message if the user query is completely unrelated to Inventory Planning>"
}}

Rules:
- If the query is unrelated to Inventory Planning, set "reorder_plan" to [] and provide the polite out-of-scope rejection and agent redirection in "summary".
- Priority rules for in-domain analysis:
  - critical: available_qty <= 0 (stockout risk)
  - high: available_qty <= reorder_point * 0.25
  - medium: available_qty <= reorder_point * 0.5
  - low: available_qty <= reorder_point
"""


# ── Helper: classify priority without LLM ────────────────────

def _classify_priority(available_qty: int, reorder_point: int) -> str:
    """Deterministic priority classification for fallback / validation."""
    if available_qty <= 0:
        return "critical"
    elif reorder_point > 0 and available_qty <= reorder_point * 0.25:
        return "high"
    elif reorder_point > 0 and available_qty <= reorder_point * 0.5:
        return "medium"
    return "low"


def _build_fallback_plan(low_stock_items: list[dict]) -> dict[str, Any]:
    """
    Generate a deterministic reorder plan without the LLM.
    Used when the LLM is unavailable or as a safety net.
    """
    plan = []
    for item in low_stock_items:
        available = item["available_qty"]
        deficit = max(0, item["reorder_point"] - item["quantity_on_hand"])
        priority = _classify_priority(available, item["reorder_point"])
        plan.append({
            "inventory_id": item["inventory_id"],
            "warehouse_code": item["warehouse_code"],
            "sku": item["sku"],
            "product_name": item["product_name"],
            "current_stock": item["quantity_on_hand"],
            "reorder_point": item["reorder_point"],
            "deficit": deficit,
            "recommended_restock_qty": max(item["reorder_qty"], deficit),
            "priority": priority,
            "justification": f"Stock ({item['quantity_on_hand']}) at or below reorder point ({item['reorder_point']}). "
                             f"Deficit of {deficit} units; restocking {max(item['reorder_qty'], deficit)} units.",
        })
    return {
        "reorder_plan": plan,
        "summary": f"{len(plan)} item(s) require restocking across warehouses.",
    }


# ── Core Agent Function ─────────────────────────────────────

async def inventory_planning_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    """
    Inventory Planning Agent — LangGraph node function.

    1. Queries the DB for items where quantity_on_hand <= reorder_point.
    2. If none found → returns state unchanged (healthy stock).
    3. If low-stock items exist → calls the LLM for a structured Reorder Plan.
    4. Falls back to a deterministic plan if the LLM fails.
    5. Logs the task to agent_task_log.
    6. Returns a partial state update dict for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict (or sub-dict).
        llm_service: Optional injected LLMService (for testability).

    Returns:
        dict with updated "inventory" sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None

    try:
        # ── Step 1: Query low-stock items ────────────────────
        low_stock_items = await execute_query(LOW_STOCK_QUERY)
        logger.info("Inventory scan complete: %d low-stock item(s) found", len(low_stock_items))

        # Serialise Decimal/datetime values from asyncpg for JSON
        low_stock_serialisable = _serialise_rows(low_stock_items)

        # ── Step 2: Healthy stock — no action needed ─────────
        # Removed early return so the LLM can answer the user's query even if stock is healthy.

        # ── Step 3: Build alerts list ────────────────────────
        alerts = [
            {
                "inventory_id": item["inventory_id"],
                "warehouse_code": item["warehouse_code"],
                "sku": item["sku"],
                "product_name": item["product_name"],
                "quantity_on_hand": item["quantity_on_hand"],
                "available_qty": item["available_qty"],
                "reorder_point": item["reorder_point"],
                "severity": _classify_priority(item["available_qty"], item["reorder_point"]),
            }
            for item in low_stock_serialisable
        ]

        # ── Step 4: Call LLM for reorder plan ────────────────
        reorder_result: dict[str, Any] | None = None

        if llm_service is None:
            llm_service = LLMService()

        try:
            user_query = state.get("query", "Provide a general inventory update.")
            prompt = REORDER_PROMPT_TEMPLATE.format(
                user_query=user_query,
                low_stock_json=json.dumps(low_stock_serialisable, indent=2) if low_stock_serialisable else "[] (Stock is healthy, no items below reorder point)",
                current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            reorder_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=4096,
            )
            logger.info("LLM reorder plan generated with %d item(s)",
                         len(reorder_result.get("reorder_plan", [])))
        except Exception as exc:
            logger.error("LLM call failed, using fallback plan: %s", exc)
            reorder_result = _build_fallback_plan(low_stock_serialisable)
            reorder_result["llm_debug_error"] = str(exc)

        # ── Step 5: Assemble state update ────────────────────
        result = {
            "inventory": {
                "low_stock_alerts": alerts,
                "reorder_recommendations": reorder_result.get("reorder_plan", []),
                "summary": reorder_result.get("summary") if reorder_result else "Inventory scan completed.",
            },
        }
        if reorder_result and "llm_debug_error" in reorder_result:
            result["inventory"]["llm_debug_error"] = reorder_result["llm_debug_error"]
            
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Inventory Planning Agent failed: %s", exc)

        # Return error in state so the supervisor can handle it
        return {
            "inventory": {
                "low_stock_alerts": [],
                "reorder_recommendations": [],
                "summary": f"Inventory Planning Agent error: {error_msg}",
            },
            "error": f"Inventory Planning Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        # Best-effort logging — don't let logging failure break the agent
        try:
            input_payload = json.dumps({"query": state.get("query", ""), "intent": state.get("intent", "")})
            output_summary = json.dumps({
                "low_stock_count": len(low_stock_items) if "low_stock_items" in dir() else 0,
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "inventory_planning",
                "stock_level_check",
                input_payload,
                output_summary,
                task_status,
                elapsed_ms,
            )
        except Exception as log_exc:
            logger.warning("Failed to log agent task: %s", log_exc)


# ── Serialisation Helpers ────────────────────────────────────

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
