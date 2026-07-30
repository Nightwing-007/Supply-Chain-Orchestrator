"""
Supply Chain Orchestrator — Application Entrypoint & REST API

Provides:
  • FastAPI server with REST endpoints for multi-agent workflow invocation
  • Standalone Single-Agent REST endpoints (Single Agent Mode: POST /api/agent/{agent_name})
  • LangGraph Supervisor Orchestrator REST endpoint (Multi Agent Mode: POST /api/workflow)
  • CORS middleware for frontend/dashboard integration
  • Lifespan context manager managing the PostgreSQL asyncpg connection pool
  • GET /health -- Service liveness probe
  • CLI mode (--cli) for terminal smoke testing
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config.settings import get_settings
from db.connection import get_pool, close_pool
from orchestrator.supervisor import run_logistics_workflow

# ── Agent Functions Import ────────────────────────────────────

from agents.inventory_agent import inventory_planning_agent
from agents.warehouse_agent import warehouse_operations_agent
from agents.demand_agent import demand_forecasting_agent
from agents.route_agent import route_optimization_agent
from agents.fleet_agent import fleet_management_agent
from agents.notification_agent import customer_notification_agent

# ── Logging Setup ────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sco.main")


# ── Standalone Agent Resolver (Single Agent Mode) ───────────────────

def get_single_agent_fn(agent_name: str) -> Optional[Callable]:
    """
    Resolve canonical or alias agent name to the corresponding async agent function.
    Evaluated dynamically to allow mock patching during unit testing.
    """
    key = agent_name.strip().lower()
    agent_map = {
        "inventory": inventory_planning_agent,
        "inventory_agent": inventory_planning_agent,
        "inventory_planning": inventory_planning_agent,

        "warehouse": warehouse_operations_agent,
        "warehouse_agent": warehouse_operations_agent,
        "warehouse_operations": warehouse_operations_agent,

        "demand": demand_forecasting_agent,
        "demand_agent": demand_forecasting_agent,
        "demand_forecasting": demand_forecasting_agent,

        "route": route_optimization_agent,
        "route_agent": route_optimization_agent,
        "route_optimization": route_optimization_agent,

        "fleet": fleet_management_agent,
        "fleet_agent": fleet_management_agent,
        "fleet_management": fleet_management_agent,

        "notification": customer_notification_agent,
        "notification_agent": customer_notification_agent,
        "customer_notification": customer_notification_agent,
    }
    return agent_map.get(key)


# ── Pydantic Request & Response Schemas ──────────────────────

class WorkflowRequest(BaseModel):
    """Request payload for starting a multi-agent logistics workflow (Multi Agent Mode)."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language user query",
        json_schema_extra={"example": "Check inventory for low stock and schedule delivery routes"},
    )
    intent: Optional[str] = Field(
        "general_check",
        description="Optional intent classification string",
        json_schema_extra={"example": "inventory_and_route"},
    )


class SingleAgentRequest(BaseModel):
    """Request payload for executing a standalone single AI agent (Single Agent Mode)."""

    query: Optional[str] = Field(
        "Execute agent task",
        description="User query or instruction prompt for the single agent",
        json_schema_extra={"example": "Check inventory stock levels"},
    )
    state: Optional[dict[str, Any]] = Field(
        None,
        description="Optional initial state input dictionary",
    )


class WorkflowResponse(BaseModel):
    """Response payload returned by orchestrator or single agent execution."""

    status: str = Field(..., description="Execution status ('success' or 'failed')")
    state: dict[str, Any] = Field(..., description="Final GlobalLogisticsState snapshot")
    final_answer: Optional[str] = Field(None, description="Human-readable executive summary")
    execution_time_ms: float = Field(..., description="Total execution duration in milliseconds")


# ── FastAPI Lifespan Manager ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    logger.info("🚀 Supply Chain Orchestrator starting up…")
    await get_pool()
    yield
    logger.info("🛑 Shutting down…")
    await close_pool()


# ── App Initialization ───────────────────────────────────────

app = FastAPI(
    title="Supply Chain Orchestrator",
    description="Smart Logistics Multi-Agent System powered by LangGraph, PostgreSQL, and Gemini",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Endpoints ────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Liveness probe to check API service health."""
    return {"status": "ok", "service": "supply-chain-orchestrator"}



@app.get("/api/dashboard", tags=["System"])
async def get_dashboard_data():
    """Fetch live metrics from PostgreSQL for the frontend dashboard."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Active Shipments
            shipments_records = await conn.fetch("""
                SELECT s.tracking_number, s.status, o.delivery_city as destination, COALESCE(s.origin, 'Mumbai Warehouse') as origin
                FROM shipments s
                JOIN orders o ON s.order_id = o.id
                WHERE s.status != 'delivered'
                ORDER BY s.id ASC
                LIMIT 10
            """)
            shipments = [dict(r) for r in shipments_records]

            # 2. Performance Data (Mocked from DB for now as example)
            performance = [
                {'name': 'Mon', 'value': 40},
                {'name': 'Tue', 'value': 60},
                {'name': 'Wed', 'value': 45},
                {'name': 'Thu', 'value': 80},
                {'name': 'Fri', 'value': 50},
                {'name': 'Sat', 'value': 90},
                {'name': 'Sun', 'value': 75},
            ]

            # 3. Flow Data (Mocked from DB for now)
            flow = [
                {'name': 'Node A', 'out': 400, 'in': 240},
                {'name': 'Node B', 'out': 300, 'in': 139},
                {'name': 'Node C', 'out': 200, 'in': 980},
                {'name': 'Node D', 'out': 278, 'in': 390},
            ]

            # 4. Risk Intel
            risks_records = await conn.fetch("""
                SELECT p.name, i.quantity_on_hand, i.reorder_point
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                WHERE i.quantity_on_hand <= i.reorder_point
                LIMIT 2
            """)
            
            risks = []
            for r in risks_records:
                risks.append({
                    "level": "Critical" if r['quantity_on_hand'] == 0 else "Warning",
                    "text": f"Low stock alert for {r['name']}: Only {r['quantity_on_hand']} left (reorder at {r['reorder_point']}).",
                })
            
            if not risks:
                risks = [{
                    "level": "Warning",
                    "text": "System running normally, but monitoring global events."
                }]

            # 5. KPI Summary Metrics
            critical_count = await conn.fetchval("""
                SELECT COUNT(*) FROM inventory WHERE quantity_on_hand <= reorder_point
            """) or 0
            total_items = await conn.fetchval("""
                SELECT COUNT(*) FROM products
            """) or 10
            avg_warehouse_fill = await conn.fetchval("""
                SELECT ROUND(AVG(used_capacity::numeric / NULLIF(total_capacity, 0)::numeric * 100), 1)
                FROM warehouses WHERE is_active = TRUE
            """) or 89.0

            # 6. Detailed Inventory Progress Metrics
            inventory_records = await conn.fetch("""
                SELECT 
                    p.sku, 
                    p.name as product_name, 
                    i.quantity_on_hand, 
                    i.reorder_point, 
                    i.reorder_qty,
                    w.code as warehouse_code
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                JOIN warehouses w ON i.warehouse_id = w.id
                ORDER BY (i.quantity_on_hand::float / NULLIF(i.reorder_point, 0)) ASC
                LIMIT 8
            """)
            inventory_items = [dict(r) for r in inventory_records]

            return {
                "shipments": shipments,
                "performance": performance,
                "flow": flow,
                "risks": risks,
                "kpis": {
                    "critical_alerts": critical_count,
                    "total_items": total_items,
                    "active_shipments": len(shipments),
                    "avg_fill_pct": float(avg_warehouse_fill),
                },
                "inventory_items": inventory_items,
            }
    except Exception as exc:
        logger.exception("Error fetching dashboard data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(exc)}",
        )


@app.post(
    "/api/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflow Orchestration (Multi Agent Mode)"],
    summary="Execute Multi-Agent LangGraph Workflow",
    description="Exposes the LangGraph Supervisor Orchestrator. Evaluates the user query, routes to appropriate single agents, and returns the unified state.",
)
async def execute_workflow(req: WorkflowRequest) -> WorkflowResponse:
    """Execute multi-agent workflow using LangGraph supervisor."""
    t0 = time.perf_counter()
    logger.info("Received workflow request: '%s' (Intent: %s)", req.query, req.intent)

    try:
        final_state = await run_logistics_workflow(
            query=req.query,
            intent=req.intent or "general_check",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        if "error" in final_state and not final_state.get("target_agent"):
            logger.error("Workflow returned error state: %s", final_state["error"])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=final_state["error"],
            )

        logger.info("Workflow completed in %.2f ms", elapsed_ms)
        return WorkflowResponse(
            status="success",
            state=final_state,
            final_answer=final_state.get("final_answer"),
            execution_time_ms=elapsed_ms,
        )

    except HTTPException:
        raise
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.exception("Internal error executing workflow: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestrator internal execution error: {str(exc)}",
        )


@app.post(
    "/api/agent/{agent_name}",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    tags=["Single Agents (Single Agent Mode)"],
    summary="Execute Standalone Single AI Agent",
    description="Invokes a specific single AI agent directly without triggering the LangGraph supervisor.",
)
async def execute_single_agent(
    agent_name: str,
    req: SingleAgentRequest,
) -> WorkflowResponse:
    """Execute a single AI agent directly (Single Agent Mode)."""
    t0 = time.perf_counter()
    canonical_key = agent_name.strip().lower()
    agent_fn = get_single_agent_fn(canonical_key)

    if agent_fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not found. Valid options: inventory, warehouse, demand, route, fleet, notification.",
        )

    input_state = dict(req.state) if req.state else {}
    if req.query:
        input_state["query"] = req.query

    logger.info("Executing standalone single agent: '%s'", canonical_key)

    try:
        updated_state = await agent_fn(input_state)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        merged_state = {**input_state, **updated_state}
        merged_state["target_agent"] = "FINISH"
        merged_state["agent_responses"] = [
            {"step": 1, "agent": canonical_key, "status": "completed", "duration_ms": elapsed_ms}
        ]

        summary = f"Standalone Single Agent '{canonical_key}' executed successfully."

        return WorkflowResponse(
            status="success",
            state=merged_state,
            final_answer=merged_state.get("final_answer") or summary,
            execution_time_ms=elapsed_ms,
        )

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.exception("Error executing single agent '%s': %s", canonical_key, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Single Agent '{canonical_key}' execution error: {str(exc)}",
        )


# ── CLI Mode ─────────────────────────────────────────────────

async def cli_mode():
    """Run a quick smoke test from the command line."""
    logger.info("Running in CLI mode…")
    pool = await get_pool()

    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        logger.info("Connected to PostgreSQL: %s", version[:60])

    await close_pool()
    logger.info("CLI smoke test passed ✅")


# ── Main Entrypoint ──────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(cli_mode())
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.environment.lower() == "development",
        )
