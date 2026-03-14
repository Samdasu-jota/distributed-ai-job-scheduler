"""
DAG-aware task scheduler.

Core responsibilities:
  1. Find tasks whose all dependencies are COMPLETED (ready tasks)
  2. Enqueue them to the correct Redis stream (idempotently)
  3. Update job status when all tasks reach a terminal state
  4. Snapshot queue metrics to PostgreSQL for Grafana time-series charts
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis

from scheduler.backoff import BackoffTracker
from shared.constants import (
    ALL_STREAMS,
    CONSUMER_GROUP,
    DEAD_LETTER_STREAM,
    STAGE_TO_STREAM,
    JobStatus,
    TaskStatus,
)
from shared import metrics as m

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Polls PostgreSQL every POLL_INTERVAL seconds to find and enqueue ready tasks.

    Idempotency guarantee:
        The UPDATE ... WHERE status='PENDING' acts as an optimistic lock.
        Even if two scheduler instances run (for HA), only one UPDATE
        succeeds per task_id due to PostgreSQL row-level locking.
    """

    def __init__(
        self,
        db: asyncpg.Pool,
        redis: aioredis.Redis,
        poll_interval: float = 2.0,
    ) -> None:
        self.db = db
        self.redis = redis
        self.poll_interval = poll_interval
        self._backoff = BackoffTracker()
        self._cleanup_counter = 0

    async def run_once(self) -> int:
        """Run one scheduler cycle. Returns number of tasks enqueued."""
        cycle_start = time.monotonic()
        enqueued_count = 0

        try:
            ready_tasks = await self._find_ready_tasks()
            m.scheduler_ready_tasks_per_cycle.observe(len(ready_tasks))

            for task in ready_tasks:
                task_id = task["id"]
                retry_count = task["retry_count"]

                # Check exponential backoff for retried tasks
                if not self._backoff.is_eligible(task_id, retry_count):
                    continue

                success = await self._enqueue_task(task)
                if success:
                    enqueued_count += 1
                    self._backoff.mark_completed(task_id)

            # Update job statuses
            await self._check_job_completions()

            # Periodic cleanup
            self._cleanup_counter += 1
            if self._cleanup_counter % 15 == 0:  # every ~30s at 2s interval
                self._backoff.cleanup()
                await self._snapshot_queue_metrics()

        except Exception as exc:
            logger.error("scheduler_cycle_error", extra={"error": str(exc)})

        cycle_duration = time.monotonic() - cycle_start
        m.scheduler_cycle_duration_seconds.observe(cycle_duration)
        return enqueued_count

    async def _find_ready_tasks(self) -> list[asyncpg.Record]:
        """
        Find all PENDING tasks whose every dependency is COMPLETED.

        The NOT EXISTS subquery checks the depends_on UUID array in one SQL
        pass — no application-side dependency resolution needed.
        Results are ordered by job priority (1=highest) to prevent
        low-priority jobs from starving high-priority ones.
        """
        async with self.db.acquire() as conn:
            return await conn.fetch(
                """
                SELECT t.id, t.job_id, t.stage_name, t.retry_count, t.max_retries
                FROM tasks t
                WHERE t.status = 'PENDING'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM tasks dep
                      WHERE dep.id = ANY(t.depends_on)
                        AND dep.status != 'COMPLETED'
                  )
                ORDER BY (
                    SELECT j.priority FROM jobs j WHERE j.id = t.job_id
                ) ASC
                LIMIT 100
                """
            )

    async def _enqueue_task(self, task: asyncpg.Record) -> bool:
        """
        Idempotently mark a task ENQUEUED and push a message to Redis.

        Returns True if this scheduler instance won the optimistic lock and
        successfully enqueued the task; False if another instance won or
        the task was already picked up.
        """
        task_id: UUID = task["id"]
        stage_name: str = task["stage_name"]
        job_id: UUID = task["job_id"]
        attempt: int = task["retry_count"] + 1

        async with self.db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tasks
                SET status = 'ENQUEUED', enqueued_at = NOW()
                WHERE id = $1 AND status = 'PENDING'
                """,
                task_id,
            )

            if result != "UPDATE 1":
                # Another process already claimed this task
                return False

            stream = STAGE_TO_STREAM[stage_name]
            message = {
                "task_id": str(task_id),
                "job_id": str(job_id),
                "stage_name": stage_name,
                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                "attempt": str(attempt),
            }
            msg_id = await self.redis.xadd(stream, message)

            # Persist Redis message ID for XCLAIM recovery
            await conn.execute(
                "UPDATE tasks SET stream_message_id = $1 WHERE id = $2",
                msg_id,
                task_id,
            )

            # Mark job as RUNNING on first enqueue
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'RUNNING', started_at = NOW()
                WHERE id = $1 AND status = 'PENDING'
                """,
                job_id,
            )

        m.scheduler_enqueue_total.labels(stage=stage_name).inc()
        logger.info(
            "task_enqueued",
            extra={
                "task_id": str(task_id),
                "stage": stage_name,
                "stream": stream,
                "attempt": attempt,
                "msg_id": msg_id,
            },
        )
        return True

    async def _check_job_completions(self) -> None:
        """Update job status when all tasks reach terminal state."""
        async with self.db.acquire() as conn:
            # Find RUNNING jobs where all tasks are in terminal states
            completable_jobs = await conn.fetch(
                """
                SELECT j.id, j.submitted_at,
                    COUNT(t.id) FILTER (WHERE t.status = 'COMPLETED') AS completed,
                    COUNT(t.id) FILTER (WHERE t.status = 'FAILED') AS failed,
                    COUNT(t.id) FILTER (WHERE t.status = 'SKIPPED') AS skipped,
                    COUNT(t.id) AS total
                FROM jobs j
                JOIN tasks t ON t.job_id = j.id
                WHERE j.status = 'RUNNING'
                GROUP BY j.id, j.submitted_at
                HAVING COUNT(t.id) = COUNT(t.id) FILTER (
                    WHERE t.status IN ('COMPLETED','FAILED','SKIPPED')
                )
                """
            )

            for job in completable_jobs:
                if job["failed"] > 0:
                    new_status = JobStatus.FAILED
                else:
                    new_status = JobStatus.COMPLETED

                await conn.execute(
                    "UPDATE jobs SET status=$1, completed_at=NOW() WHERE id=$2",
                    new_status,
                    job["id"],
                )

                e2e_seconds = (
                    datetime.now(timezone.utc) - job["submitted_at"].replace(tzinfo=timezone.utc)
                ).total_seconds()
                m.job_total.labels(status=new_status.lower()).inc()
                m.job_e2e_duration_seconds.observe(e2e_seconds)

                logger.info(
                    "job_completed",
                    extra={
                        "job_id": str(job["id"]),
                        "status": new_status,
                        "e2e_seconds": round(e2e_seconds, 2),
                    },
                )

    async def _snapshot_queue_metrics(self) -> None:
        """Write Redis stream depths to queue_metrics table for Grafana."""
        async with self.db.acquire() as conn:
            for stream in ALL_STREAMS:
                try:
                    length = await self.redis.xlen(stream)
                    try:
                        pending_info = await self.redis.xpending(stream, CONSUMER_GROUP)
                        pending = pending_info.get("pending", 0) if pending_info else 0
                    except Exception:
                        pending = 0

                    # Update Prometheus gauge
                    m.queue_depth_pending.labels(stream=stream).set(length)

                    await conn.execute(
                        """
                        INSERT INTO queue_metrics
                            (stream_name, pending_count, consumer_group, active_consumers)
                        VALUES ($1, $2, $3, $4)
                        """,
                        stream,
                        pending,
                        CONSUMER_GROUP,
                        0,  # consumer count updated separately by heartbeat monitor
                    )
                except Exception as exc:
                    logger.warning(
                        "queue_snapshot_error",
                        extra={"stream": stream, "error": str(exc)},
                    )
