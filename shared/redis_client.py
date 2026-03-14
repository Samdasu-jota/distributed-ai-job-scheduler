"""
Redis async client factory using redis.asyncio.

Consumer groups are initialized here at startup so all services
share the same group names defined in constants.py.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import redis.asyncio as aioredis

from shared.constants import ALL_STREAMS, CONSUMER_GROUP, DEAD_LETTER_STREAM

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis = aioredis.from_url(url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def init_consumer_groups() -> None:
    """
    Create consumer groups on all task streams (idempotent).

    Uses MKSTREAM so streams are created if they don't exist yet.
    The '$' start ID means new groups only consume messages created after
    group creation — existing backlog (if any) is ignored on first start.
    """
    redis = await get_redis()
    streams = ALL_STREAMS + [DEAD_LETTER_STREAM]
    for stream in streams:
        try:
            await redis.xgroup_create(stream, CONSUMER_GROUP, id="$", mkstream=True)
            logger.info("consumer_group_created", extra={"stream": stream, "group": CONSUMER_GROUP})
        except aioredis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists — normal on restart
            else:
                raise
