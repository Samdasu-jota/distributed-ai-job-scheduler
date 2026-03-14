"""
Heartbeat monitor — detects dead workers and reclaims their in-flight tasks.

Runs as a periodic coroutine inside the scheduler event loop.
Every HEARTBEAT_TIMEOUT_SECONDS, it:
  1. Marks workers DEAD if last_heartbeat is stale
  2. Finds tasks stuck in RUNNING for a dead worker
  3. Resets those tasks to PENDING so the scheduler re-enqueues them
  4. Issues XCLAIM on their Redis stream messages to remove them from the PEL
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis

from shared.constants import CONSUMER_GROUP, STAGE_TO_STREAM

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "30"))
DEAD_MESSAGE_CLAIM_AFTER = int(os.getenv("DEAD_MESSAGE_CLAIM_AFTER", "60")) * 1000  # ms


async def run_heartbeat_monitor(db: asyncpg.Pool, redis: aioredis.Redis) -> None:
    """
    Detect dead workers and reclaim their tasks.
    Call this in a periodic loop from the scheduler's main loop.
    """
    async with db.acquire() as conn:
        # 1. Mark workers DEAD if heartbeat is stale
        dead_worker_ids = await conn.fetch(
            """
            UPDATE workers
            SET status = 'DEAD'
            WHERE status != 'DEAD'
              AND last_heartbeat < NOW() - MAKE_INTERVAL(secs => $1)
            RETURNING id, hostname, current_task_id
            """,
            float(HEARTBEAT_TIMEOUT),
        )

        if dead_worker_ids:
            for row in dead_worker_ids:
                logger.warning(
                    "worker_declared_dead",
                    extra={"worker_id": str(row["id"]), "hostname": row["hostname"]},
                )

        # 2. Find RUNNING tasks whose worker is now DEAD
        stuck_tasks = await conn.fetch(
            """
            SELECT t.id, t.stage_name, t.retry_count, t.max_retries,
                   t.stream_message_id, t.job_id
            FROM tasks t
            JOIN workers w ON t.worker_id = w.id
            WHERE t.status = 'RUNNING'
              AND w.status = 'DEAD'
            """
        )

        for task in stuck_tasks:
            task_id: UUID = task["id"]
            retry_count: int = task["retry_count"]
            max_retries: int = task["max_retries"]
            msg_id: str | None = task["stream_message_id"]

            if retry_count >= max_retries:
                # Exhausted — mark FAILED
                await conn.execute(
                    """
                    UPDATE tasks SET status='FAILED', completed_at=NOW(),
                        error='Worker died; max retries exhausted'
                    WHERE id=$1
                    """,
                    task_id,
                )
                logger.error(
                    "task_failed_dead_worker",
                    extra={"task_id": str(task_id), "stage": task["stage_name"]},
                )
            else:
                # Reset to PENDING so scheduler re-enqueues with backoff
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status='PENDING', retry_count=retry_count+1,
                        worker_id=NULL, error='Worker died; will retry'
                    WHERE id=$1 AND status='RUNNING'
                    """,
                    task_id,
                )
                logger.info(
                    "task_reset_for_retry",
                    extra={
                        "task_id": str(task_id),
                        "stage": task["stage_name"],
                        "attempt": retry_count + 1,
                    },
                )

                # 3. XCLAIM the old Redis message to remove it from PEL
                if msg_id:
                    stream = STAGE_TO_STREAM.get(task["stage_name"])
                    if stream:
                        try:
                            # Claim it and immediately delete it so scheduler
                            # can add a fresh message on next cycle
                            await redis.xclaim(
                                stream,
                                CONSUMER_GROUP,
                                "heartbeat-monitor",
                                DEAD_MESSAGE_CLAIM_AFTER,
                                [msg_id],
                            )
                            await redis.xack(stream, CONSUMER_GROUP, msg_id)
                        except Exception as exc:
                            logger.warning(
                                "xclaim_failed",
                                extra={"msg_id": msg_id, "error": str(exc)},
                            )
