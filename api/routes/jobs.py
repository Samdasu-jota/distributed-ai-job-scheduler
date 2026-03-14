"""
Job management routes.

POST /api/jobs            — Submit a new job (creates job + all tasks with DAG depends_on)
GET  /api/jobs            — List jobs (filterable by status)
GET  /api/jobs/{job_id}   — Get job + all task statuses
GET  /api/jobs/{job_id}/dag — DAG visualization data (nodes + edges)
DELETE /api/jobs/{job_id} — Cancel a running job
WS   /ws/jobs/{job_id}   — Live task-status stream for a specific job
WS   /ws/dashboard        — Aggregate queue/worker broadcast
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from api.schemas.jobs import (
    DAGEdge,
    DAGNode,
    DAGResponse,
    JobListResponse,
    JobResponse,
    JobSubmitRequest,
    TaskStatusResponse,
)
from api.websocket.manager import manager
from shared.constants import ALL_STAGES, MAX_RETRIES_BY_STAGE, STAGE_DAG, JobStatus, TaskStatus
from shared.db import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_db() -> asyncpg.Pool:
    return await get_pool()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_task_response(row: asyncpg.Record) -> TaskStatusResponse:
    return TaskStatusResponse(
        task_id=str(row["id"]),
        stage_name=row["stage_name"],
        status=row["status"],
        depends_on=[str(d) for d in (row["depends_on"] or [])],
        enqueued_at=row["enqueued_at"].isoformat() if row["enqueued_at"] else None,
        started_at=row["started_at"].isoformat() if row["started_at"] else None,
        completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
        worker_id=str(row["worker_id"]) if row["worker_id"] else None,
        retry_count=row["retry_count"],
        error=row["error"],
    )


def _row_to_job_response(
    job_row: asyncpg.Record,
    task_rows: list[asyncpg.Record],
) -> JobResponse:
    return JobResponse(
        job_id=str(job_row["id"]),
        status=job_row["status"],
        submitted_at=job_row["submitted_at"].isoformat(),
        started_at=job_row["started_at"].isoformat() if job_row["started_at"] else None,
        completed_at=job_row["completed_at"].isoformat() if job_row["completed_at"] else None,
        user_id=job_row["user_id"],
        priority=job_row["priority"],
        tasks=[_row_to_task_response(t) for t in task_rows],
    )


# ── POST /api/jobs ─────────────────────────────────────────────────────────────

@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobSubmitRequest, db: asyncpg.Pool = Depends(get_db)) -> JobResponse:
    """
    Submit a new English tutoring job.

    Creates one job row and one task row per pipeline stage (7 total).
    The depends_on column is populated with actual task UUIDs resolved from
    STAGE_DAG, encoding the full DAG into the database at creation time.
    """
    async with db.acquire() as conn:
        async with conn.transaction():
            # 1. Insert job
            job_id: UUID = await conn.fetchval(
                """
                INSERT INTO jobs (input_data, user_id, priority)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                json.dumps({
                    "audio_url": body.audio_url,
                    "duration_ms": body.duration_ms,
                    "session_id": body.session_id,
                }),
                body.user_id,
                body.priority,
            )

            # 2. Insert all task rows (no depends_on yet — need UUIDs first)
            task_ids: dict[str, UUID] = {}
            for stage_name in ALL_STAGES:
                task_id: UUID = await conn.fetchval(
                    """
                    INSERT INTO tasks (job_id, stage_name, max_retries)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    job_id,
                    stage_name,
                    MAX_RETRIES_BY_STAGE[stage_name],
                )
                task_ids[stage_name] = task_id

            # 3. Update depends_on using resolved UUIDs
            for stage_name, dep_stages in STAGE_DAG.items():
                dep_uuids = [task_ids[d] for d in dep_stages]
                await conn.execute(
                    "UPDATE tasks SET depends_on = $1 WHERE id = $2",
                    dep_uuids,
                    task_ids[stage_name],
                )

            # 4. Fetch the created rows to return
            task_rows = await conn.fetch(
                "SELECT * FROM tasks WHERE job_id = $1 ORDER BY stage_name",
                job_id,
            )
            job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

    logger.info("job_created", extra={"job_id": str(job_id), "user_id": body.user_id})
    return _row_to_job_response(job_row, task_rows)


# ── GET /api/jobs ──────────────────────────────────────────────────────────────

@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: asyncpg.Pool = Depends(get_db),
) -> JobListResponse:
    async with db.acquire() as conn:
        if status:
            jobs = await conn.fetch(
                "SELECT * FROM jobs WHERE status = $1 ORDER BY submitted_at DESC LIMIT $2 OFFSET $3",
                status.upper(), limit, offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM jobs WHERE status = $1", status.upper()
            )
        else:
            jobs = await conn.fetch(
                "SELECT * FROM jobs ORDER BY submitted_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM jobs")

        responses = []
        for job_row in jobs:
            task_rows = await conn.fetch(
                "SELECT * FROM tasks WHERE job_id = $1 ORDER BY stage_name",
                job_row["id"],
            )
            responses.append(_row_to_job_response(job_row, task_rows))

    return JobListResponse(jobs=responses, total=total)


# ── GET /api/jobs/{job_id} ─────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: asyncpg.Pool = Depends(get_db)) -> JobResponse:
    async with db.acquire() as conn:
        job_row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", UUID(job_id))
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")
        task_rows = await conn.fetch(
            "SELECT * FROM tasks WHERE job_id = $1 ORDER BY stage_name",
            UUID(job_id),
        )
    return _row_to_job_response(job_row, task_rows)


# ── GET /api/jobs/{job_id}/dag ─────────────────────────────────────────────────

@router.get("/{job_id}/dag", response_model=DAGResponse)
async def get_job_dag(job_id: str, db: asyncpg.Pool = Depends(get_db)) -> DAGResponse:
    """Return DAG node/edge structure for frontend ReactFlow visualization."""
    async with db.acquire() as conn:
        job_row = await conn.fetchrow("SELECT id FROM jobs WHERE id = $1", UUID(job_id))
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")
        task_rows = await conn.fetch(
            "SELECT * FROM tasks WHERE job_id = $1",
            UUID(job_id),
        )

    # Build id → task_id mapping for edge construction
    stage_to_task_id = {row["stage_name"]: str(row["id"]) for row in task_rows}

    nodes = [
        DAGNode(
            id=str(row["id"]),
            stage_name=row["stage_name"],
            status=row["status"],
            depends_on=[str(d) for d in (row["depends_on"] or [])],
            started_at=row["started_at"].isoformat() if row["started_at"] else None,
            completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
            worker_id=str(row["worker_id"]) if row["worker_id"] else None,
            retry_count=row["retry_count"],
        )
        for row in task_rows
    ]

    edges = []
    for stage_name, dep_stages in STAGE_DAG.items():
        target_id = stage_to_task_id.get(stage_name)
        for dep_stage in dep_stages:
            source_id = stage_to_task_id.get(dep_stage)
            if source_id and target_id:
                edges.append(DAGEdge(source=source_id, target=target_id))

    return DAGResponse(job_id=job_id, nodes=nodes, edges=edges)


# ── DELETE /api/jobs/{job_id} ──────────────────────────────────────────────────

@router.delete("/{job_id}", status_code=200)
async def cancel_job(job_id: str, db: asyncpg.Pool = Depends(get_db)) -> dict:
    async with db.acquire() as conn:
        async with conn.transaction():
            job_row = await conn.fetchrow("SELECT status FROM jobs WHERE id = $1", UUID(job_id))
            if not job_row:
                raise HTTPException(status_code=404, detail="Job not found")
            if job_row["status"] in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                raise HTTPException(
                    status_code=409,
                    detail=f"Job is already in terminal state: {job_row['status']}",
                )
            await conn.execute(
                "UPDATE jobs SET status='CANCELLED', completed_at=NOW() WHERE id=$1",
                UUID(job_id),
            )
            await conn.execute(
                """
                UPDATE tasks
                SET status='SKIPPED'
                WHERE job_id=$1
                  AND status IN ('PENDING', 'ENQUEUED')
                """,
                UUID(job_id),
            )
    logger.info("job_cancelled", extra={"job_id": job_id})
    return {"job_id": job_id, "status": "CANCELLED"}


# ── WebSocket: /ws/jobs/{job_id} ───────────────────────────────────────────────

@router.websocket("/ws/jobs/{job_id}")
async def ws_job_updates(websocket: WebSocket, job_id: str) -> None:
    await manager.connect_job(websocket, job_id)
    try:
        while True:
            # Keep connection alive; updates are pushed from scheduler/workers
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_job(websocket, job_id)


# ── WebSocket: /ws/dashboard ───────────────────────────────────────────────────

@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket) -> None:
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)
