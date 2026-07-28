"""
Supply Chain Orchestrator — Application Entrypoint & REST API

Provides:
  • FastAPI server with REST endpoints for multi-agent workflow invocation
  • CORS middleware for frontend/dashboard integration
  • Lifespan context manager managing the PostgreSQL asyncpg connection pool
  • POST /api/workflow -- LangGraph Supervisor Orchestrator endpoint
  • GET /health -- Service liveness probe
  • CLI mode (--cli) for terminal smoke testing
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from config.settings import get_settings
from db.connection import get_pool, close_pool
from orchestrator.supervisor import run_logistics_workflow

# ── Logging Setup ────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sco.main")


# ── Pydantic Request & Response Schemas ──────────────────────

class WorkflowRequest(BaseModel):
    """Request payload for starting a multi-agent logistics workflow."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language user query (e.g. 'Check low stock and schedule delivery routes')",
        json_schema_extra={"example": "Check inventory for low stock and schedule delivery routes"},
    )
    intent: Optional[str] = Field(
        "general_check",
        description="Optional intent classification string",
        json_schema_extra={"example": "inventory_and_route"},
    )


class WorkflowResponse(BaseModel):
    """Response payload returned by the LangGraph supervisor workflow."""

    status: str = Field(..., description="Workflow execution status ('success' or 'failed')")
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

# Enable CORS for all origins (dashboard & external clients)
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


@app.post(
    "/api/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    tags=["Workflow Orchestration"],
    summary="Execute Multi-Agent Logistics Workflow",
    description="Exposes the LangGraph Supervisor Orchestrator. Evaluates the user query, routes to appropriate single agents, and returns the unified state.",
)
async def execute_workflow(req: WorkflowRequest) -> WorkflowResponse:
    """
    Execute the multi-agent workflow for the given user query.

    Args:
        req: WorkflowRequest containing the query and optional intent.

    Returns:
        WorkflowResponse with the final GlobalLogisticsState and execution metadata.
    """
    t0 = time.perf_counter()
    logger.info("Received workflow request: '%s' (Intent: %s)", req.query, req.intent)

    try:
        final_state = await run_logistics_workflow(
            query=req.query,
            intent=req.intent or "general_check",
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Check if the final state produced a top-level error
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
        logger.exception("Internal error executing workflow for query '%s': %s", req.query, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orchestrator internal execution error: {str(exc)}",
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
