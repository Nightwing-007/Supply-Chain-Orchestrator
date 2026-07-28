"""
Tests for FastAPI REST API (main.py)

Covers:
  1. GET /health endpoint returns 200 OK.
  2. Test Case 1: Successful POST /api/workflow returns 200 OK and mocked GlobalLogisticsState response payload.
  3. Test Case 2: Invalid or empty query payload returns 422 Unprocessable Entity validation error.
  4. Test Case 3: Simulated internal orchestrator failure returns 500 Internal Server Error.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


# =============================================================
#  Test 1: Health Check Probe
# =============================================================

@pytest.mark.asyncio
async def test_health_check_endpoint():
    """GET /health should return 200 OK and status 'ok'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "supply-chain-orchestrator"


# =============================================================
#  Test Case 1: Successful Workflow POST (200 OK)
# =============================================================

@pytest.mark.asyncio
@patch("main.run_logistics_workflow", new_callable=AsyncMock)
async def test_workflow_post_success(mock_run_workflow):
    """POST /api/workflow with a valid query returns 200 OK and WorkflowResponse payload."""
    mock_run_workflow.return_value = {
        "query": "Check inventory stock levels",
        "intent": "inventory_check",
        "target_agent": "FINISH",
        "final_answer": "Inventory check completed. 2 items low on stock.",
        "inventory": {
            "low_stock_alerts": [
                {"sku": "SKU-HOME-001", "quantity_on_hand": 3, "reorder_point": 5}
            ],
            "reorder_recommendations": [],
        },
        "agent_responses": [
            {"step": 1, "agent": "inventory_agent", "status": "completed"},
            {"step": 2, "agent": "supervisor", "next_agent": "FINISH"},
        ],
    }

    payload = {
        "query": "Check inventory stock levels",
        "intent": "inventory_check",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/workflow", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["final_answer"] == "Inventory check completed. 2 items low on stock."
        assert "execution_time_ms" in data
        assert data["state"]["target_agent"] == "FINISH"
        assert "inventory" in data["state"]

    mock_run_workflow.assert_called_once_with(
        query="Check inventory stock levels",
        intent="inventory_check",
    )


# =============================================================
#  Test Case 2: Validation Error (422 Unprocessable Entity)
# =============================================================

@pytest.mark.asyncio
async def test_workflow_post_invalid_empty_query():
    """POST /api/workflow with empty string query returns 422 Unprocessable Entity."""
    payload = {
        "query": "",  # Violation of min_length=1
        "intent": "inventory_check",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/workflow", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_workflow_post_missing_query_field():
    """POST /api/workflow with missing query field returns 422 Unprocessable Entity."""
    payload = {
        "intent": "inventory_check",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/workflow", json=payload)
        assert response.status_code == 422


# =============================================================
#  Test Case 3: Internal Orchestrator Failure (500 Internal Server Error)
# =============================================================

@pytest.mark.asyncio
@patch("main.run_logistics_workflow", new_callable=AsyncMock)
async def test_workflow_post_internal_error(mock_run_workflow):
    """If run_logistics_workflow raises an unexpected exception, endpoint returns 500 Internal Server Error."""
    mock_run_workflow.side_effect = RuntimeError("Database connection pool closed unexpectedly")

    payload = {
        "query": "Check fleet status",
        "intent": "fleet_check",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/workflow", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Database connection pool closed unexpectedly" in data["detail"]
