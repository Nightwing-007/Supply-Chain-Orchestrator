"""
Tests for FastAPI REST API (main.py)

Covers:
  1. GET /health endpoint returns 200 OK.
  2. POST /api/workflow returns 200 OK with mocked GlobalLogisticsState payload (Multi Agent Mode).
  3. POST /api/workflow 422 Unprocessable Entity on validation error.
  4. POST /api/workflow 500 Internal Server Error on orchestrator failure.
  5. POST /api/agent/{agent_name} returns 200 OK with single agent state (Single Agent Mode).
  6. POST /api/agent/{invalid_name} returns 404 Not Found.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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
#  Test 2: Workflow POST (Multi Agent Mode)
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


# =============================================================
#  Test 3: Standalone Single Agent POST (Single Agent Mode)
# =============================================================

@pytest.mark.asyncio
@patch("main.inventory_planning_agent", new_callable=AsyncMock)
async def test_single_agent_post_success(mock_inventory_agent):
    """POST /api/agent/inventory directly invokes the inventory agent and returns 200 OK."""
    mock_inventory_agent.return_value = {
        "inventory": {
            "low_stock_alerts": [{"sku": "SKU-TEST-1", "quantity_on_hand": 2}],
            "reorder_recommendations": [],
        }
    }

    payload = {
        "query": "Check low stock items",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/inventory", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "inventory" in data["state"]
        assert data["state"]["target_agent"] == "FINISH"

    mock_inventory_agent.assert_called_once()


@pytest.mark.asyncio
async def test_single_agent_post_not_found():
    """POST /api/agent/unknown_agent returns 404 Not Found."""
    payload = {"query": "Check stuff"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/unknown_agent", json=payload)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================
#  Test 4: Shop Owner Login & Auth Endpoint
# =============================================================

@pytest.mark.asyncio
async def test_login_success():
    """POST /api/login with admin/password123 returns 200 OK and auth token."""
    payload = {"username": "admin", "password": "password123"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "token" in data
        assert data["username"] == "admin"


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """POST /api/login with wrong password returns 401 Unauthorized."""
    payload = {"username": "admin", "password": "wrongpassword"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/login", json=payload)
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


# =============================================================
#  Test 5: Product Deletion & Products API
# =============================================================

@pytest.mark.asyncio
@patch("main.get_pool")
async def test_delete_product_not_found(mock_get_pool):
    """DELETE /api/products/99999 returns 404 Not Found."""
    mock_trans = MagicMock()
    mock_trans.__aenter__ = AsyncMock(return_value=None)
    mock_trans.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None  # Product does not exist
    mock_conn.transaction = MagicMock(return_value=mock_trans)

    mock_acq = MagicMock()
    mock_acq.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acq.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acq)
    mock_get_pool.return_value = mock_pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/products/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

