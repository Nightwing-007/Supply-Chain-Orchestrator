"""
Agent 3: Demand Forecasting Agent

Responsibilities:
  - Aggregate historical sales via PostgreSQL window functions
    (rolling 7-day and 30-day averages computed at the DB layer)
  - Calculate algorithmic baseline forecast using Exponential Smoothing
  - Detect high-volatility products (7-day avg >> 30-day avg)
  - Invoke LLM for qualitative adjustment of baseline forecasts
  - Fall back to pure algorithmic baseline when LLM is unavailable

Node interface (LangGraph-ready):
  Input:  dict  -- GlobalLogisticsState (or its demand sub-state)
  Output: dict  -- partial state update with { "demand": DemandState }
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

DEFAULT_ALPHA = 0.3            # Exponential smoothing factor (0 < alpha <= 1)
VOLATILITY_THRESHOLD = 1.5     # 7d avg / 30d avg ratio that flags volatility
FORECAST_PERIOD_DAYS = 7       # Default forecast horizon

# -- SQL Queries ----------------------------------------------

ROLLING_SALES_QUERY = """
    WITH daily_sales AS (
        SELECT
            oi.product_id,
            p.sku,
            p.name               AS product_name,
            p.category,
            DATE(o.placed_at)    AS sale_date,
            SUM(oi.quantity)     AS daily_qty
        FROM order_items oi
        JOIN orders   o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id
        WHERE o.status NOT IN ('cancelled')
          AND o.placed_at >= NOW() - INTERVAL '90 days'
          AND p.is_active = TRUE
        GROUP BY oi.product_id, p.sku, p.name, p.category, DATE(o.placed_at)
    ),
    product_agg AS (
        SELECT
            product_id,
            sku,
            product_name,
            category,
            sale_date,
            daily_qty,
            AVG(daily_qty) OVER (
                PARTITION BY product_id
                ORDER BY sale_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS rolling_avg_7d,
            AVG(daily_qty) OVER (
                PARTITION BY product_id
                ORDER BY sale_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
            ) AS rolling_avg_30d,
            SUM(daily_qty) OVER (
                PARTITION BY product_id
            ) AS total_sold_90d,
            COUNT(*) OVER (
                PARTITION BY product_id
            ) AS active_sale_days
        FROM daily_sales
    )
    SELECT DISTINCT ON (product_id)
        product_id,
        sku,
        product_name,
        category,
        sale_date              AS latest_sale_date,
        daily_qty              AS latest_daily_qty,
        rolling_avg_7d,
        rolling_avg_30d,
        total_sold_90d,
        active_sale_days
    FROM product_agg
    ORDER BY product_id, sale_date DESC
"""

HISTORICAL_DAILY_QUERY = """
    SELECT
        oi.product_id,
        DATE(o.placed_at)      AS sale_date,
        SUM(oi.quantity)       AS daily_qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.status NOT IN ('cancelled')
      AND o.placed_at >= NOW() - INTERVAL '90 days'
    GROUP BY oi.product_id, DATE(o.placed_at)
    ORDER BY oi.product_id, DATE(o.placed_at)
"""

LOG_AGENT_TASK = """
    INSERT INTO agent_task_log (agent, task_type, input_payload, output_payload, status, duration_ms, completed_at)
    VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, NOW())
"""


# =============================================================
#  Exponential Smoothing
# =============================================================

def exponential_smoothing(
    observations: list[float],
    alpha: float = DEFAULT_ALPHA,
) -> float:
    """
    Simple Exponential Smoothing (SES) for time-series forecasting.

    Formula:  S_t = alpha * Y_t + (1 - alpha) * S_{t-1}

    The forecast for the next period is the final smoothed value.

    Args:
        observations: Chronologically ordered daily quantities.
        alpha: Smoothing factor (0 < alpha <= 1).
               Higher alpha = more weight on recent data.

    Returns:
        Forecast value for the next period.
    """
    if not observations:
        return 0.0

    if len(observations) == 1:
        return observations[0]

    # Initialise S_0 with the first observation
    smoothed = observations[0]

    for y_t in observations[1:]:
        smoothed = alpha * y_t + (1.0 - alpha) * smoothed

    return smoothed


def calculate_confidence(
    active_sale_days: int,
    rolling_avg_7d: float,
    rolling_avg_30d: float,
) -> float:
    """
    Heuristic confidence score for a forecast (0.0 - 1.0).

    Factors:
      - More data points -> higher confidence
      - Lower volatility (7d close to 30d) -> higher confidence
    """
    # Data sufficiency component (0-0.5): maxes out at 60+ sale days
    data_score = min(active_sale_days / 60.0, 1.0) * 0.5

    # Stability component (0-0.5): ratio close to 1.0 is ideal
    if rolling_avg_30d > 0:
        ratio = rolling_avg_7d / rolling_avg_30d
        # Perfect stability = ratio of 1.0 -> score 0.5
        # Deviation penalised exponentially
        stability_score = max(0.0, 0.5 * math.exp(-abs(ratio - 1.0)))
    else:
        stability_score = 0.0

    return round(min(data_score + stability_score, 1.0), 4)


def detect_volatility(
    rolling_avg_7d: float,
    rolling_avg_30d: float,
    threshold: float = VOLATILITY_THRESHOLD,
) -> dict[str, Any]:
    """
    Detect if a product shows high sales volatility.

    Returns:
        Dict with ``is_volatile``, ``ratio``, and ``direction``.
    """
    if rolling_avg_30d <= 0:
        return {"is_volatile": False, "ratio": 0.0, "direction": "stable"}

    ratio = rolling_avg_7d / rolling_avg_30d

    if ratio >= threshold:
        return {"is_volatile": True, "ratio": round(ratio, 2), "direction": "surging"}
    elif ratio <= (1.0 / threshold):
        return {"is_volatile": True, "ratio": round(ratio, 2), "direction": "declining"}
    else:
        return {"is_volatile": False, "ratio": round(ratio, 2), "direction": "stable"}


def build_baseline_forecasts(
    aggregated_rows: list[dict[str, Any]],
    daily_history: dict[int, list[float]],
    alpha: float = DEFAULT_ALPHA,
) -> list[dict[str, Any]]:
    """
    Build algorithmic baseline forecasts for all products using
    Exponential Smoothing on historical daily sales.

    Args:
        aggregated_rows: Output from ROLLING_SALES_QUERY (serialised).
        daily_history: Map of product_id -> chronological daily quantities.
        alpha: Smoothing factor.

    Returns:
        List of forecast dicts with baseline predictions and metadata.
    """
    forecasts = []

    for row in aggregated_rows:
        pid = row["product_id"]
        observations = daily_history.get(pid, [])
        avg_7d = float(row.get("rolling_avg_7d", 0) or 0)
        avg_30d = float(row.get("rolling_avg_30d", 0) or 0)
        active_days = int(row.get("active_sale_days", 0) or 0)

        # Exponential smoothing on daily observations
        ses_forecast = exponential_smoothing(observations, alpha)

        # Weekly forecast = daily forecast * 7
        weekly_forecast = round(ses_forecast * FORECAST_PERIOD_DAYS)

        # Confidence and volatility
        confidence = calculate_confidence(active_days, avg_7d, avg_30d)
        volatility = detect_volatility(avg_7d, avg_30d)

        forecasts.append({
            "product_id": pid,
            "sku": row["sku"],
            "product_name": row["product_name"],
            "category": row.get("category", ""),
            "rolling_avg_7d": round(avg_7d, 2),
            "rolling_avg_30d": round(avg_30d, 2),
            "total_sold_90d": int(row.get("total_sold_90d", 0) or 0),
            "active_sale_days": active_days,
            "ses_daily_forecast": round(ses_forecast, 2),
            "baseline_weekly_forecast": weekly_forecast,
            "confidence": confidence,
            "volatility": volatility,
            "forecast_period_days": FORECAST_PERIOD_DAYS,
        })

    # Sort: volatile products first, then by total sold descending
    forecasts.sort(key=lambda f: (
        -int(f["volatility"]["is_volatile"]),
        -f["total_sold_90d"],
    ))

    return forecasts


# =============================================================
#  LLM Integration
# =============================================================

SYSTEM_INSTRUCTION = """You are a senior supply chain demand planner specializing in statistical forecasting and market trend analysis.
Analyse algorithmic baseline forecasts and apply qualitative adjustments based on trends, seasonality, and volatility signals.

DOMAIN GUARDRAILS:
Evaluate the user's query. If the query is completely unrelated to your specific domain (Demand Forecasting, sales trends, historical sales analysis, sales volatility), you MUST NOT process the state data or generate your standard report. Instead, return a polite message stating that this task is outside your scope as the Demand Forecasting Agent in the "summary" field, leave "adjusted_forecasts" and "market_insights" empty [], and explicitly suggest which of the other specific agents (Inventory Planning, Warehouse Ops, Route Optimization, Fleet Management, Customer Notification) they should select from the dropdown, or suggest switching to the Multi-Agent Supervisor.

Always respond with valid JSON matching the schema provided."""

ADJUSTMENT_PROMPT_TEMPLATE = """Analyse the following user request and baseline demand forecasts to produce an Adjusted Forecast Plan or evaluate domain relevance.

## User Request / Query
{user_query}

## Baseline Forecasts (Exponential Smoothing, alpha={alpha})
{baseline_json}

## Products Flagged as Volatile
{volatile_json}

## Current Date
{current_date}

## Required Output Schema
Return a JSON object with this exact structure:
{{
  "adjusted_forecasts": [
    {{
      "product_id": <int>,
      "sku": "<string>",
      "baseline_weekly_forecast": <int>,
      "adjusted_weekly_forecast": <int>,
      "adjustment_pct": <float>,
      "adjustment_reason": "<brief justification>",
      "trend_signal": "<surging|stable|declining|seasonal>"
    }}
  ],
  "market_insights": [
    "<string: one-sentence insight about overall demand patterns>"
  ],
  "summary": "<executive summary of demand outlook if in-domain, OR a polite out-of-scope redirection message if the user query is completely unrelated to Demand Forecasting>"
}}

Rules:
- If the query is unrelated to Demand Forecasting, set "adjusted_forecasts" to [] and "market_insights" to [], and provide the polite out-of-scope rejection and redirection in "summary".
- Only adjust forecasts where you have a clear qualitative reason.
- If a product is stable, keep adjusted_weekly_forecast == baseline_weekly_forecast and set adjustment_pct to 0.
- adjustment_pct = ((adjusted - baseline) / baseline) * 100. Positive = upward revision.
- Be conservative: adjustments > +/- 30% require strong justification.
"""


def _build_fallback_adjusted(baseline_forecasts: list[dict]) -> dict[str, Any]:
    """
    Deterministic fallback: return baseline forecasts as-is with no adjustments.
    """
    adjusted = []
    for fc in baseline_forecasts:
        adjusted.append({
            "product_id": fc["product_id"],
            "sku": fc["sku"],
            "baseline_weekly_forecast": fc["baseline_weekly_forecast"],
            "adjusted_weekly_forecast": fc["baseline_weekly_forecast"],
            "adjustment_pct": 0.0,
            "adjustment_reason": "No LLM adjustment available; using pure algorithmic baseline.",
            "trend_signal": fc["volatility"]["direction"],
        })
    return {
        "adjusted_forecasts": adjusted,
        "market_insights": [
            "Forecast generated using pure Exponential Smoothing baseline (LLM unavailable).",
        ],
        "summary": f"Baseline forecasts for {len(adjusted)} product(s). No qualitative adjustments applied.",
    }


# =============================================================
#  Core Agent Function
# =============================================================

async def demand_forecasting_agent(
    state: dict[str, Any],
    *,
    llm_service: LLMService | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """
    Demand Forecasting Agent -- LangGraph node function.

    Pipeline:
      1. Query rolling 7d/30d averages via PostgreSQL window functions.
      2. Query daily sales history for Exponential Smoothing input.
      3. Compute baseline forecasts with SES.
      4. Detect volatile products.
      5. Call LLM for qualitative adjustments (with fallback).
      6. Log execution to agent_task_log.
      7. Return partial state update for GlobalLogisticsState.

    Args:
        state: Current GlobalLogisticsState dict.
        llm_service: Optional injected LLMService (for testability).
        alpha: Exponential smoothing factor.

    Returns:
        dict with updated ``demand`` sub-state.
    """
    t0 = time.perf_counter()
    task_status = "completed"
    error_msg = None
    product_count = 0

    try:
        # -- Step 1: Rolling averages (window functions) ------
        aggregated_rows = await execute_query(ROLLING_SALES_QUERY)
        aggregated_serialised = _serialise_rows(aggregated_rows)
        product_count = len(aggregated_serialised)
        logger.info("Aggregated sales data for %d product(s)", product_count)

        # -- Step 2: Daily history for SES --------------------
        daily_rows = await execute_query(HISTORICAL_DAILY_QUERY)
        daily_serialised = _serialise_rows(daily_rows)

        # Build per-product chronological observation lists
        daily_history: dict[int, list[float]] = {}
        for row in daily_serialised:
            pid = row["product_id"]
            daily_history.setdefault(pid, []).append(float(row["daily_qty"]))

        # -- Step 3: Baseline forecasts -----------------------
        baseline_forecasts = build_baseline_forecasts(
            aggregated_serialised, daily_history, alpha=alpha
        )
        logger.info("Computed %d baseline forecast(s)", len(baseline_forecasts))

        # -- Step 4: Identify volatile products ---------------
        volatile_products = [
            f for f in baseline_forecasts if f["volatility"]["is_volatile"]
        ]
        logger.info("Detected %d volatile product(s)", len(volatile_products))

        # -- Step 5: No data scenario -------------------------
        if not baseline_forecasts:
            return {
                "demand": {
                    "forecast_period_days": FORECAST_PERIOD_DAYS,
                    "historical_data": [],
                    "forecast_results": [],
                },
            }

        # -- Step 6: LLM qualitative adjustment ---------------
        adjustment_result: dict[str, Any]

        if llm_service is None:
            llm_service = LLMService()

        try:
            user_query = state.get("query", "Provide a demand forecast.")
            prompt = ADJUSTMENT_PROMPT_TEMPLATE.format(
                user_query=user_query,
                alpha=alpha,
                baseline_json=json.dumps(baseline_forecasts, indent=2),
                volatile_json=json.dumps(volatile_products, indent=2) if volatile_products
                    else "None -- all products show stable demand patterns.",
                current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
            adjustment_result = await llm_service.generate(
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.25,
                max_output_tokens=4096,
            )
            logger.info(
                "LLM adjusted %d forecast(s)",
                len(adjustment_result.get("adjusted_forecasts", [])),
            )
        except Exception as exc:
            logger.error("LLM call failed, using baseline fallback: %s", exc)
            adjustment_result = _build_fallback_adjusted(baseline_forecasts)

        # -- Step 7: Assemble state update --------------------
        forecast_results = adjustment_result.get("adjusted_forecasts", [])

        # Merge confidence from baseline into final results
        baseline_map = {f["product_id"]: f for f in baseline_forecasts}
        for fr in forecast_results:
            pid = fr.get("product_id")
            if pid in baseline_map:
                fr["confidence"] = baseline_map[pid]["confidence"]
                fr["ses_daily_forecast"] = baseline_map[pid]["ses_daily_forecast"]
                fr["rolling_avg_7d"] = baseline_map[pid]["rolling_avg_7d"]
                fr["rolling_avg_30d"] = baseline_map[pid]["rolling_avg_30d"]

        result: dict[str, Any] = {
            "demand": {
                "forecast_period_days": FORECAST_PERIOD_DAYS,
                "historical_data": baseline_forecasts,
                "forecast_results": forecast_results,
                "summary": adjustment_result.get("summary", ""),
                # Extended metadata
                "_volatile_products": volatile_products,
                "_market_insights": adjustment_result.get("market_insights", []),
                "_summary": adjustment_result.get("summary", ""),
            },
        }
        return result

    except Exception as exc:
        task_status = "failed"
        error_msg = str(exc)
        logger.exception("Demand Forecasting Agent failed: %s", exc)
        return {
            "demand": {
                "forecast_period_days": FORECAST_PERIOD_DAYS,
                "historical_data": [],
                "forecast_results": [],
            },
            "error": f"Demand Forecasting Agent error: {error_msg}",
        }

    finally:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        try:
            input_payload = json.dumps({
                "query": state.get("query", ""),
                "intent": state.get("intent", ""),
                "alpha": alpha,
            })
            output_summary = json.dumps({
                "products_forecasted": product_count,
                "status": task_status,
            })
            await execute_command(
                LOG_AGENT_TASK,
                "demand_forecasting",
                "demand_forecast",
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
