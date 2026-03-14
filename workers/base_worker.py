"""
BaseWorker — the core distributed worker loop.

Every stage-specific worker inherits from this class. It handles:
  - Worker registration in the workers table on startup
  - Heartbeat thread (every WORKER_HEARTBEAT_INTERVAL seconds)
  - XREADGROUP blocking loop — true push semantics via Redis Streams
  - Idempotent task claim (UPDATE WHERE status='ENQUEUED')
  - Upstream input fetching from PostgreSQL result_json
  - Result persistence and task COMPLETED transition
  - Retry logic: reset to PENDING with incremented retry_count
  - Dead-letter routing when retries exhausted
  - Prometheus metrics emission

Design: Each worker process handles ONE task at a time (count=1 in XREADGROUP).
Horizontal scaling is achieved by adding more container replicas — they compete
through the same Redis consumer group and each gets unique tasks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as aioredis

from shared.constants import (
    CONSUMER_GROUP,
    DEAD_LETTER_STREAM,
    STAGE_TO_STREAM,
    TaskStatus,
)
from shared import metrics as m

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "10"))
BLOCK_TIMEOUT_MS = 5000  # XREADGROUP block timeout; loops back to retry


class BaseWorker(ABC):
    """
    Abstract base class for all stage workers.

    Subclasses must implement:
        stage_name: str    — one of the ALL_STAGES values
        execute(input_data) → dict   — the stage logic
    """

    stage_name: str  # set by subclass

    def __init__(self) -> None:
        self.worker_id: UUID | None = None
        self.hostname = socket.gethostname()
        self.db: asyncpg.Pool | None = None
        self.redis: aioredis.Redis | None = None
        self._running = True
        self._heartbeat_thread: threading.Thread | None = None

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the stage logic. input_data comes from upstream task result_json."""

    @property
    def stream_name(self) -> str:
        return STAGE_TO_STREAM[self.stage_name]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        from shared.db import create_pool
        from shared.redis_client import get_redis

        self.db = await create_pool()
        self.redis = await get_redis()

        await self._register()
        self._start_heartbeat()
        logger.info(
            "worker_started",
            extra={
                "worker_id": str(self.worker_id),
                "stage": self.stage_name,
                "stream": self.stream_name,
                "hostname": self.hostname,
            },
        )
        await self._run_loop()

    async def _register(self) -> None:
        async with self.db.acquire() as conn:
            self.worker_id = await conn.fetchval(
                """
                INSERT INTO workers (hostname, worker_type, status)
                VALUES ($1, $2, 'IDLE')
                ON CONFLICT (hostname) DO UPDATE
                    SET status='IDLE', last_heartbeat=NOW(), worker_type=$2
                RETURNING id
                """,
                self.hostname,
                self.stage_name,
            )

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        """Blocking thread; updates last_heartbeat in PostgreSQL."""
        loop = asyncio.new_event_loop()
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            try:
                loop.run_until_complete(self._send_heartbeat())
            except Exception as exc:
                logger.warning("heartbeat_error", extra={"error": str(exc)})
        loop.close()

    async def _send_heartbeat(self) -> None:
        async with self.db.acquire() as conn:
            await conn.execute(
                "UPDATE workers SET last_heartbeat=NOW() WHERE id=$1",
                self.worker_id,
            )

    # ── Main XREADGROUP Loop ──────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        consumer_name = f"{self.stage_name}-{self.hostname}"

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={self.stream_name: ">"},
                    count=1,
                    block=BLOCK_TIMEOUT_MS,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, data in entries:
                        await self._process_message(msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("worker_loop_error", extra={"error": str(exc)})
                await asyncio.sleep(1)

    # ── Message Processing ────────────────────────────────────────────────────

    async def _process_message(self, msg_id: str, data: dict[str, str]) -> None:
        # Filter to tasks matching this worker's stage
        # (nlp workers get both nlp_processing and grammar_correction)
        task_stage = data.get("stage_name", "")
        if not self._handles_stage(task_stage):
            # Requeue for correct consumer — shouldn't happen with proper stream routing
            await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)
            return

        task_id = UUID(data["task_id"])
        job_id = data["job_id"]
        attempt = int(data.get("attempt", "1"))

        # Idempotent claim — only one worker wins per task
        async with self.db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tasks
                SET status='RUNNING', started_at=NOW(), worker_id=$1
                WHERE id=$2 AND status='ENQUEUED'
                """,
                self.worker_id,
                task_id,
            )
            if result != "UPDATE 1":
                # Another worker instance claimed it (consumer group protects against
                # this, but be defensive)
                await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)
                return

            await conn.execute(
                "UPDATE workers SET status='BUSY', current_task_id=$1 WHERE id=$2",
                task_id,
                self.worker_id,
            )

        stage_start = time.monotonic()

        try:
            # Fetch aggregated inputs from all upstream tasks
            input_data = await self._fetch_inputs(task_id)

            # Execute the stage logic
            result_data = await self.execute(input_data)

            # Persist result and mark COMPLETED
            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status='COMPLETED', completed_at=NOW(), result_json=$1
                    WHERE id=$2
                    """,
                    json.dumps(result_data),
                    task_id,
                )
                await conn.execute(
                    """
                    UPDATE workers
                    SET status='IDLE', current_task_id=NULL,
                        tasks_completed=tasks_completed+1
                    WHERE id=$1
                    """,
                    self.worker_id,
                )

            # ACK the Redis message
            await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)

            # Emit metrics
            stage_duration = time.monotonic() - stage_start
            m.task_duration_seconds.labels(stage=task_stage).observe(stage_duration)
            m.worker_task_total.labels(
                worker_type=self.stage_name, stage=task_stage, status="completed"
            ).inc()

            logger.info(
                "task_completed",
                extra={
                    "task_id": str(task_id),
                    "stage": task_stage,
                    "duration_ms": round(stage_duration * 1000, 1),
                    "attempt": attempt,
                },
            )

        except Exception as exc:
            await self._handle_failure(task_id, msg_id, task_stage, exc)

    def _handles_stage(self, stage_name: str) -> bool:
        """
        Return True if this worker should handle the given stage.
        Subclasses override this for workers that handle multiple stages
        (e.g., NLPWorker handles both nlp_processing and grammar_correction).
        """
        return stage_name == self.stage_name

    # ── Input Fetching ────────────────────────────────────────────────────────

    async def _fetch_inputs(self, task_id: UUID) -> dict[str, Any]:
        """
        Fetch result_json from all upstream (depends_on) tasks.

        Merges all upstream result_json dicts into a single flat dict.
        This means downstream stages get all data from all prior stages
        without having to know about the DAG structure explicitly.
        """
        async with self.db.acquire() as conn:
            task_row = await conn.fetchrow(
                "SELECT depends_on, job_id FROM tasks WHERE id=$1",
                task_id,
            )
            if not task_row or not task_row["depends_on"]:
                # First stage — fetch job input_data
                job_row = await conn.fetchrow(
                    "SELECT input_data FROM jobs WHERE id=$1",
                    task_row["job_id"] if task_row else None,
                )
                if job_row:
                    return json.loads(job_row["input_data"])
                return {}

            # Fetch all upstream results and merge
            upstream_tasks = await conn.fetch(
                "SELECT stage_name, result_json FROM tasks WHERE id = ANY($1)",
                task_row["depends_on"],
            )

            # Also fetch job input_data for base context
            job_row = await conn.fetchrow(
                "SELECT input_data FROM jobs WHERE id=$1",
                task_row["job_id"],
            )
            merged: dict[str, Any] = {}
            if job_row:
                merged.update(json.loads(job_row["input_data"]))

            for upstream in upstream_tasks:
                if upstream["result_json"]:
                    result = upstream["result_json"]
                    if isinstance(result, str):
                        result = json.loads(result)
                    merged.update(result)

        return merged

    # ── Failure Handling ──────────────────────────────────────────────────────

    async def _handle_failure(
        self,
        task_id: UUID,
        msg_id: str,
        stage_name: str,
        exc: Exception,
    ) -> None:
        error_msg = str(exc)
        logger.error(
            "task_failed",
            extra={"task_id": str(task_id), "stage": stage_name, "error": error_msg},
        )

        async with self.db.acquire() as conn:
            task_row = await conn.fetchrow(
                "SELECT retry_count, max_retries, job_id FROM tasks WHERE id=$1",
                task_id,
            )
            if not task_row:
                await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)
                return

            retry_count = task_row["retry_count"]
            max_retries = task_row["max_retries"]

            if retry_count < max_retries:
                # Reset to PENDING — scheduler will re-enqueue with backoff
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status='PENDING', retry_count=retry_count+1,
                        worker_id=NULL, error=$1
                    WHERE id=$2 AND status='RUNNING'
                    """,
                    error_msg,
                    task_id,
                )
                await conn.execute(
                    """
                    UPDATE workers
                    SET status='IDLE', current_task_id=NULL,
                        tasks_failed=tasks_failed+1
                    WHERE id=$1
                    """,
                    self.worker_id,
                )
                # ACK old message — scheduler will add a fresh one
                await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)

                m.worker_task_total.labels(
                    worker_type=self.stage_name, stage=stage_name, status="retried"
                ).inc()

            else:
                # Exhausted retries — dead letter
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status='FAILED', completed_at=NOW(), error=$1
                    WHERE id=$2
                    """,
                    error_msg,
                    task_id,
                )
                await conn.execute(
                    """
                    UPDATE workers
                    SET status='IDLE', current_task_id=NULL,
                        tasks_failed=tasks_failed+1
                    WHERE id=$1
                    """,
                    self.worker_id,
                )

                # Write to dead-letter stream
                await self.redis.xadd(
                    DEAD_LETTER_STREAM,
                    {
                        "task_id": str(task_id),
                        "job_id": str(task_row["job_id"]),
                        "stage_name": stage_name,
                        "error": error_msg,
                        "exhausted_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                await self.redis.xack(self.stream_name, CONSUMER_GROUP, msg_id)

                m.worker_task_total.labels(
                    worker_type=self.stage_name, stage=stage_name, status="failed"
                ).inc()
                logger.error(
                    "task_dead_lettered",
                    extra={"task_id": str(task_id), "stage": stage_name},
                )
