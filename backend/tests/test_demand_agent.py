"""
Tests for Agent 3: Demand Forecasting Agent

Covers:
  1. Exponential Smoothing correctness (multiple cases)
  2. Confidence score calculation
  3. Volatility detection (surging, declining, stable, edge cases)
  4. Baseline forecast builder (full pipeline)
  5. Happy path -- full agent with LLM adjustment
  6. LLM failure -- deterministic baseline fallback
  7. No sales data -- empty result scenario
  8. DB failure -- error state propagation
  9. State key validation against GlobalLogisticsState
  10. Fallback adjusted plan structure
"""

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.demand_agent import (
    demand_forecasting_agent,
    exponential_smoothing,
    calculate_confidence,
    detect_volatility,
    build_baseline_forecasts,
    _build_fallback_adjusted,
    _serialise_rows,
    DEFAULT_ALPHA,
    VOLATILITY_THRESHOLD,
    FORECAST_PERIOD_DAYS,
)


# =============================================================
#  Fixtures
# =============================================================

SAMPLE_AGGREGATED_ROWS = [
    {
        "product_id": 1,
        "sku": "SKU-ELEC-001",
        "product_name": "Wireless Bluetooth Headphones",
        "category": "Electronics",
        "latest_sale_date": date(2026, 7, 26),
        "latest_daily_qty": 15,
        "rolling_avg_7d": Decimal("18.50"),
        "rolling_avg_30d": Decimal("12.00"),
        "total_sold_90d": 1080,
        "active_sale_days": 72,
    },
    {
        "product_id": 6,
        "sku": "SKU-GROC-001",
        "product_name": "Organic Green Tea (100 bags)",
        "category": "Grocery",
        "latest_sale_date": date(2026, 7, 25),
        "latest_daily_qty": 5,
        "rolling_avg_7d": Decimal("5.20"),
        "rolling_avg_30d": Decimal("5.00"),
        "total_sold_90d": 450,
        "active_sale_days": 85,
    },
    {
        "product_id": 8,
        "sku": "SKU-APRL-001",
        "product_name": "Men's Running Shoes (Size 10)",
        "category": "Apparel",
        "latest_sale_date": date(2026, 7, 24),
        "latest_daily_qty": 2,
        "rolling_avg_7d": Decimal("8.00"),
        "rolling_avg_30d": Decimal("3.00"),
        "total_sold_90d": 270,
        "active_sale_days": 45,
    },
]

SAMPLE_DAILY_ROWS = [
    # Product 1: trending up
    {"product_id": 1, "sale_date": date(2026, 7, 20), "daily_qty": 10},
    {"product_id": 1, "sale_date": date(2026, 7, 21), "daily_qty": 11},
    {"product_id": 1, "sale_date": date(2026, 7, 22), "daily_qty": 13},
    {"product_id": 1, "sale_date": date(2026, 7, 23), "daily_qty": 14},
    {"product_id": 1, "sale_date": date(2026, 7, 24), "daily_qty": 16},
    {"product_id": 1, "sale_date": date(2026, 7, 25), "daily_qty": 17},
    {"product_id": 1, "sale_date": date(2026, 7, 26), "daily_qty": 15},
    # Product 6: stable
    {"product_id": 6, "sale_date": date(2026, 7, 23), "daily_qty": 5},
    {"product_id": 6, "sale_date": date(2026, 7, 24), "daily_qty": 5},
    {"product_id": 6, "sale_date": date(2026, 7, 25), "daily_qty": 5},
    # Product 8: spiking
    {"product_id": 8, "sale_date": date(2026, 7, 22), "daily_qty": 2},
    {"product_id": 8, "sale_date": date(2026, 7, 23), "daily_qty": 3},
    {"product_id": 8, "sale_date": date(2026, 7, 24), "daily_qty": 2},
]

SAMPLE_LLM_ADJUSTMENT = {
    "adjusted_forecasts": [
        {
            "product_id": 1,
            "sku": "SKU-ELEC-001",
            "baseline_weekly_forecast": 100,
            "adjusted_weekly_forecast": 120,
            "adjustment_pct": 20.0,
            "adjustment_reason": "Strong upward trend in last 7 days suggests continued demand surge.",
            "trend_signal": "surging",
        },
        {
            "product_id": 6,
            "sku": "SKU-GROC-001",
            "baseline_weekly_forecast": 35,
            "adjusted_weekly_forecast": 35,
            "adjustment_pct": 0.0,
            "adjustment_reason": "Stable demand pattern. No adjustment needed.",
            "trend_signal": "stable",
        },
        {
            "product_id": 8,
            "sku": "SKU-APRL-001",
            "baseline_weekly_forecast": 16,
            "adjusted_weekly_forecast": 22,
            "adjustment_pct": 37.5,
            "adjustment_reason": "7-day avg is 2.67x the 30-day avg. Possible viral/seasonal trend.",
            "trend_signal": "surging",
        },
    ],
    "market_insights": [
        "Electronics demand shows sustained growth driven by seasonal promotions.",
        "Apparel category experiencing unexpected spike -- monitor for sustainability.",
    ],
    "summary": "Overall demand is trending upward. 2 of 3 products show elevated short-term demand.",
}

EMPTY_STATE: dict = {"query": "Forecast demand", "intent": "demand_forecast"}


# =============================================================
#  Test 1: Exponential Smoothing
# =============================================================

class TestExponentialSmoothing:
    """Unit tests for the SES implementation."""

    def test_single_observation(self):
        """Single data point: forecast equals the observation."""
        assert exponential_smoothing([42.0]) == 42.0

    def test_empty_observations(self):
        """No data: forecast is 0."""
        assert exponential_smoothing([]) == 0.0

    def test_constant_series(self):
        """Constant series: forecast equals the constant."""
        result = exponential_smoothing([10.0, 10.0, 10.0, 10.0], alpha=0.3)
        assert abs(result - 10.0) < 1e-9

    def test_trending_up(self):
        """Upward trend: forecast should be above the mean."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = exponential_smoothing(data, alpha=0.5)
        mean = sum(data) / len(data)
        # With alpha=0.5 weighting recent data more, result > mean
        assert result > mean

    def test_alpha_1_uses_last_value(self):
        """alpha=1.0 means S_t = Y_t (pure last-value forecast)."""
        data = [10.0, 20.0, 30.0, 5.0]
        result = exponential_smoothing(data, alpha=1.0)
        assert result == 5.0

    def test_alpha_near_zero_uses_first_value(self):
        """alpha close to 0 heavily weights the initial value."""
        data = [100.0, 1.0, 1.0, 1.0, 1.0]
        result = exponential_smoothing(data, alpha=0.01)
        # Should be much closer to 100 than to 1
        assert result > 50.0

    def test_manual_calculation(self):
        """Verify against a hand-calculated example with alpha=0.3."""
        data = [10.0, 12.0, 15.0]
        alpha = 0.3
        # S_0 = 10.0
        # S_1 = 0.3 * 12 + 0.7 * 10 = 3.6 + 7.0 = 10.6
        # S_2 = 0.3 * 15 + 0.7 * 10.6 = 4.5 + 7.42 = 11.92
        expected = 11.92
        result = exponential_smoothing(data, alpha=alpha)
        assert abs(result - expected) < 0.01


# =============================================================
#  Test 2: Confidence Score
# =============================================================

class TestConfidenceScore:
    """Unit tests for the heuristic confidence scoring."""

    def test_high_data_stable(self):
        """Many data points + stable ratio -> high confidence."""
        score = calculate_confidence(80, 10.0, 10.0)
        assert score > 0.8

    def test_low_data(self):
        """Few data points -> lower confidence."""
        score = calculate_confidence(5, 10.0, 10.0)
        assert score < 0.6

    def test_high_volatility_reduces_confidence(self):
        """Large 7d/30d divergence reduces confidence."""
        stable = calculate_confidence(60, 10.0, 10.0)
        volatile = calculate_confidence(60, 30.0, 10.0)  # 3x ratio
        assert volatile < stable

    def test_zero_30d_avg(self):
        """Zero 30-day average: stability component is 0."""
        score = calculate_confidence(60, 5.0, 0.0)
        # Only data_score contributes: min(60/60, 1) * 0.5 = 0.5
        assert abs(score - 0.5) < 0.01

    def test_bounded_0_to_1(self):
        """Score must always be between 0 and 1."""
        for days in [0, 1, 30, 100]:
            for avg7 in [0, 1, 50, 200]:
                for avg30 in [0, 1, 50]:
                    score = calculate_confidence(days, avg7, avg30)
                    assert 0.0 <= score <= 1.0


# =============================================================
#  Test 3: Volatility Detection
# =============================================================

class TestVolatilityDetection:
    """Unit tests for the volatility detector."""

    def test_surging(self):
        """7d avg much higher than 30d avg -> surging."""
        result = detect_volatility(30.0, 10.0)
        assert result["is_volatile"] is True
        assert result["direction"] == "surging"
        assert result["ratio"] == 3.0

    def test_declining(self):
        """7d avg much lower than 30d avg -> declining."""
        result = detect_volatility(2.0, 10.0)
        assert result["is_volatile"] is True
        assert result["direction"] == "declining"

    def test_stable(self):
        """Similar averages -> stable."""
        result = detect_volatility(10.0, 9.0)
        assert result["is_volatile"] is False
        assert result["direction"] == "stable"

    def test_zero_30d(self):
        """Zero 30d average is not volatile (no baseline)."""
        result = detect_volatility(5.0, 0.0)
        assert result["is_volatile"] is False

    def test_exact_threshold(self):
        """At exactly the threshold ratio."""
        result = detect_volatility(15.0, 10.0, threshold=1.5)
        assert result["is_volatile"] is True
        assert result["direction"] == "surging"

    def test_just_below_threshold(self):
        result = detect_volatility(14.0, 10.0, threshold=1.5)
        assert result["is_volatile"] is False
        assert result["direction"] == "stable"


# =============================================================
#  Test 4: Baseline Forecast Builder
# =============================================================

class TestBaselineForecasts:
    """Integration test for the full baseline forecast pipeline."""

    def test_builds_correct_count(self):
        agg = _serialise_rows(SAMPLE_AGGREGATED_ROWS)
        daily = _serialise_rows(SAMPLE_DAILY_ROWS)
        history = _build_daily_history(daily)
        forecasts = build_baseline_forecasts(agg, history)
        assert len(forecasts) == 3

    def test_volatile_products_sorted_first(self):
        agg = _serialise_rows(SAMPLE_AGGREGATED_ROWS)
        daily = _serialise_rows(SAMPLE_DAILY_ROWS)
        history = _build_daily_history(daily)
        forecasts = build_baseline_forecasts(agg, history)

        # Product 8 (surging: 8.0/3.0 = 2.67x) and Product 1 (1.54x) should appear before Product 6
        volatile_flags = [f["volatility"]["is_volatile"] for f in forecasts]
        # All volatile ones should be at the front
        first_stable_idx = next(
            (i for i, v in enumerate(volatile_flags) if not v),
            len(volatile_flags),
        )
        # No stable product should appear before a volatile one
        for i in range(first_stable_idx, len(volatile_flags)):
            assert not volatile_flags[i] or i < first_stable_idx

    def test_weekly_forecast_is_7x_daily(self):
        agg = _serialise_rows(SAMPLE_AGGREGATED_ROWS[:1])  # just product 1
        daily = _serialise_rows(SAMPLE_DAILY_ROWS[:7])     # product 1 data
        history = _build_daily_history(daily)
        forecasts = build_baseline_forecasts(agg, history)

        fc = forecasts[0]
        expected_weekly = round(fc["ses_daily_forecast"] * 7)
        assert fc["baseline_weekly_forecast"] == expected_weekly
        assert fc["forecast_period_days"] == FORECAST_PERIOD_DAYS

    def test_empty_input(self):
        assert build_baseline_forecasts([], {}) == []

    def test_no_history_for_product(self):
        """Product in aggregation but no daily history -> SES forecast = 0."""
        agg = [{
            "product_id": 99,
            "sku": "SKU-NONE",
            "product_name": "Ghost Product",
            "category": "Unknown",
            "rolling_avg_7d": 0,
            "rolling_avg_30d": 0,
            "total_sold_90d": 0,
            "active_sale_days": 0,
        }]
        forecasts = build_baseline_forecasts(agg, {})
        assert forecasts[0]["ses_daily_forecast"] == 0.0
        assert forecasts[0]["baseline_weekly_forecast"] == 0


# =============================================================
#  Test 5: Full Agent -- Happy Path with LLM
# =============================================================

@pytest.mark.asyncio
@patch("agents.demand_agent.execute_command", new_callable=AsyncMock)
@patch("agents.demand_agent.execute_query", new_callable=AsyncMock)
async def test_happy_path_with_llm(mock_query, mock_log_cmd):
    """Full pipeline: DB -> SES baseline -> LLM adjustment."""
    mock_query.side_effect = [
        SAMPLE_AGGREGATED_ROWS,
        SAMPLE_DAILY_ROWS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_ADJUSTMENT)

    result = await demand_forecasting_agent(EMPTY_STATE, llm_service=mock_llm)

    # LLM was called
    mock_llm.generate.assert_called_once()

    # Structure checks
    assert "demand" in result
    demand = result["demand"]
    assert demand["forecast_period_days"] == FORECAST_PERIOD_DAYS
    assert len(demand["historical_data"]) == 3
    assert len(demand["forecast_results"]) == 3
    assert "_volatile_products" in demand
    assert "_market_insights" in demand

    # Adjusted forecasts should have merged confidence
    for fr in demand["forecast_results"]:
        assert "confidence" in fr
        assert "ses_daily_forecast" in fr

    # No error
    assert "error" not in result


# =============================================================
#  Test 6: LLM Failure -> Baseline Fallback
# =============================================================

@pytest.mark.asyncio
@patch("agents.demand_agent.execute_command", new_callable=AsyncMock)
@patch("agents.demand_agent.execute_query", new_callable=AsyncMock)
async def test_llm_failure_uses_baseline(mock_query, mock_log_cmd):
    """When LLM fails, agent returns pure algorithmic baseline."""
    mock_query.side_effect = [
        SAMPLE_AGGREGATED_ROWS,
        SAMPLE_DAILY_ROWS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("API timeout"))

    result = await demand_forecasting_agent(EMPTY_STATE, llm_service=mock_llm)

    assert "error" not in result
    demand = result["demand"]

    # Forecast results should match baseline (adjustment_pct = 0)
    for fr in demand["forecast_results"]:
        assert fr["adjustment_pct"] == 0.0
        assert fr["adjusted_weekly_forecast"] == fr["baseline_weekly_forecast"]
        assert "algorithmic baseline" in fr["adjustment_reason"].lower()


# =============================================================
#  Test 7: No Sales Data
# =============================================================

@pytest.mark.asyncio
@patch("agents.demand_agent.execute_command", new_callable=AsyncMock)
@patch("agents.demand_agent.execute_query", new_callable=AsyncMock)
async def test_no_sales_data(mock_query, mock_log_cmd):
    """When no historical sales exist, return empty forecasts."""
    mock_query.side_effect = [
        [],  # no aggregated rows
        [],  # no daily rows
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()

    result = await demand_forecasting_agent(EMPTY_STATE, llm_service=mock_llm)

    # LLM should NOT have been called
    mock_llm.generate.assert_not_called()

    assert result["demand"]["forecast_results"] == []
    assert result["demand"]["historical_data"] == []
    assert "error" not in result


# =============================================================
#  Test 8: DB Failure
# =============================================================

@pytest.mark.asyncio
@patch("agents.demand_agent.execute_command", new_callable=AsyncMock)
@patch("agents.demand_agent.execute_query", new_callable=AsyncMock)
async def test_db_failure_returns_error(mock_query, mock_log_cmd):
    """Database failure propagates as error in state."""
    mock_query.side_effect = ConnectionError("Connection refused")
    mock_log_cmd.return_value = "INSERT 0 1"

    result = await demand_forecasting_agent(EMPTY_STATE)

    assert "error" in result
    assert "Connection refused" in result["error"]
    assert result["demand"]["forecast_results"] == []
    assert result["demand"]["historical_data"] == []


# =============================================================
#  Test 9: State Key Validation
# =============================================================

@pytest.mark.asyncio
@patch("agents.demand_agent.execute_command", new_callable=AsyncMock)
@patch("agents.demand_agent.execute_query", new_callable=AsyncMock)
async def test_state_keys_match_global_state(mock_query, mock_log_cmd):
    """All returned keys must be valid GlobalLogisticsState members."""
    mock_query.side_effect = [
        SAMPLE_AGGREGATED_ROWS,
        SAMPLE_DAILY_ROWS,
    ]
    mock_log_cmd.return_value = "INSERT 0 1"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=SAMPLE_LLM_ADJUSTMENT)

    result = await demand_forecasting_agent(EMPTY_STATE, llm_service=mock_llm)

    valid_top_keys = {
        "query", "intent", "target_agent",
        "inventory", "warehouse", "fleet", "demand", "route", "notification",
        "agent_responses", "error", "final_answer",
    }
    for key in result.keys():
        assert key in valid_top_keys, f"Unexpected top-level key '{key}'"

    # Core DemandState keys
    demand = result["demand"]
    required_keys = {"forecast_period_days", "historical_data", "forecast_results"}
    assert required_keys.issubset(demand.keys()), f"Missing: {required_keys - demand.keys()}"


# =============================================================
#  Test 10: Fallback Plan Structure
# =============================================================

class TestFallbackAdjusted:
    """Verify the deterministic fallback produces valid structure."""

    def test_structure(self):
        baseline = [
            {
                "product_id": 1,
                "sku": "SKU-A",
                "baseline_weekly_forecast": 50,
                "volatility": {"is_volatile": False, "ratio": 1.0, "direction": "stable"},
            },
            {
                "product_id": 2,
                "sku": "SKU-B",
                "baseline_weekly_forecast": 30,
                "volatility": {"is_volatile": True, "ratio": 2.0, "direction": "surging"},
            },
        ]
        result = _build_fallback_adjusted(baseline)

        assert "adjusted_forecasts" in result
        assert "market_insights" in result
        assert "summary" in result
        assert len(result["adjusted_forecasts"]) == 2

    def test_no_adjustments_applied(self):
        baseline = [
            {
                "product_id": 1,
                "sku": "SKU-A",
                "baseline_weekly_forecast": 75,
                "volatility": {"is_volatile": False, "ratio": 1.0, "direction": "stable"},
            },
        ]
        result = _build_fallback_adjusted(baseline)

        fc = result["adjusted_forecasts"][0]
        assert fc["adjusted_weekly_forecast"] == 75
        assert fc["baseline_weekly_forecast"] == 75
        assert fc["adjustment_pct"] == 0.0
        assert fc["trend_signal"] == "stable"


# =============================================================
#  Helper
# =============================================================

def _build_daily_history(rows: list[dict]) -> dict[int, list[float]]:
    """Build per-product daily history from serialised rows."""
    history: dict[int, list[float]] = {}
    for row in rows:
        pid = row["product_id"]
        history.setdefault(pid, []).append(float(row["daily_qty"]))
    return history
