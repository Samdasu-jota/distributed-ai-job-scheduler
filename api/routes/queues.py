"""Queue depth and metrics routes."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from shared.constants import ALL_STREAMS, CONSUMER_GROUP
from shared.db import get_pool
from shared.redis_client import get_redis

router = APIRouter(prefix="/api/queues", tags=["queues"])


async def get_db() -> asyncpg.Pool:
    return await get_pool()


@router.get("")
async def get_queue_depths() -> dict:
    """Return pending message count for each task stream."""
    redis = await get_redis()
    result = {}
    for stream in ALL_STREAMS:
        try:
            # XPENDING returns summary: {count, min-id, max-id, consumers}
            pending_info = await redis.xpending(stream, CONSUMER_GROUP)
            # XLEN returns total messages in the stream
            length = await redis.xlen(stream)
            result[stream] = {
                "stream": stream,
                "total_messages": length,
                "pending_ack": pending_info.get("pending", 0) if pending_info else 0,
            }
        except Exception:
            result[stream] = {"stream": stream, "total_messages": 0, "pending_ack": 0}
    return {"queues": list(result.values())}


@router.get("/history")
async def get_queue_history(limit: int = 100, db: asyncpg.Pool = Depends(get_db)) -> dict:
    """Historical queue depth snapshots for time-series charting."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT captured_at, stream_name, pending_count, active_consumers
            FROM queue_metrics
            ORDER BY captured_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "history": [
            {
                "captured_at": r["captured_at"].isoformat(),
                "stream_name": r["stream_name"],
                "pending_count": r["pending_count"],
                "active_consumers": r["active_consumers"],
            }
            for r in rows
        ]
    }
