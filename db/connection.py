"""
Supply Chain Orchestrator — Async PostgreSQL Connection Pool

Provides a singleton asyncpg connection pool used by all agents
and services for non-blocking database access.
"""

import asyncpg
import logging
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Module-level pool reference (singleton)
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        settings = get_settings()
        logger.info("Creating asyncpg connection pool → %s", settings.database_url)
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=30,
            server_settings={"search_path": "sco,public"},
        )
        logger.info("Connection pool created (min=%d, max=%d)", settings.db_pool_min_size, settings.db_pool_max_size)
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed.")


async def execute_query(query: str, *args) -> list[dict]:
    """Execute a SELECT query and return results as list of dicts."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def execute_one(query: str, *args) -> Optional[dict]:
    """Execute a query and return a single row as dict, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def execute_command(query: str, *args) -> str:
    """Execute an INSERT/UPDATE/DELETE and return the command status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def execute_in_transaction(queries: list[tuple[str, tuple]]) -> None:
    """
    Execute multiple statements inside a single transaction.

    Args:
        queries: List of (sql, args) tuples.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for sql, args in queries:
                await conn.execute(sql, *args)
