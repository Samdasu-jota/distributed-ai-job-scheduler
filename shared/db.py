"""
asyncpg connection pool factory.

Usage:
    pool = await create_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT ...")
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def create_pool(dsn: Optional[str] = None) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        url = dsn or os.environ["DATABASE_URL"]
        _pool = await asyncpg.create_pool(
            dsn=url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        await create_pool()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
