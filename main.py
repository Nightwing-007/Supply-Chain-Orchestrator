"""
Supply Chain Orchestrator — Application Entrypoint

Provides:
  • A FastAPI server for HTTP-based agent invocation
  • CLI mode for direct agent testing
  • Lifecycle hooks for DB pool creation/teardown
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from config.settings import get_settings
from db.connection import get_pool, close_pool

# ── Logging ──────────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sco.main")


# ── FastAPI Lifecycle ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("🚀 Supply Chain Orchestrator starting up…")
    await get_pool()
    yield
    logger.info("🛑 Shutting down…")
    await close_pool()


app = FastAPI(
    title="Supply Chain Orchestrator",
    description="Smart Logistics Multi-Agent System",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Health Check ─────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    """Liveness probe."""
    return {"status": "ok", "service": "supply-chain-orchestrator"}


# ── CLI Mode ─────────────────────────────────────────────────

async def cli_mode():
    """Run a quick smoke test from the command line."""
    logger.info("Running in CLI mode…")
    pool = await get_pool()

    # Quick DB connectivity test
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        logger.info("Connected to PostgreSQL: %s", version[:60])

    await close_pool()
    logger.info("CLI smoke test passed ✅")


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--cli" in sys.argv:
        asyncio.run(cli_mode())
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.environment == "development",
        )
