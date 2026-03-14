"""Prometheus metrics and throughput analytics routes."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from shared.db import get_pool

router = APIRouter(tags=["metrics"])


async def get_db() -> asyncpg.Pool:
    return await get_pool()


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@router.get("/api/metrics/throughput")
async def throughput_metrics(db: asyncpg.Pool = Depends(get_db)) -> dict:
    """Jobs and tasks completed per minute over the last hour."""
    async with db.acquire() as conn:
        jobs_per_min = await conn.fetch(
            """
            SELECT
                date_trunc('minute', completed_at) AS minute,
                COUNT(*) AS jobs_completed
            FROM jobs
            WHERE completed_at >= NOW() - INTERVAL '1 hour'
              AND status = 'COMPLETED'
            GROUP BY 1
            ORDER BY 1
            """
        )
        tasks_per_min = await conn.fetch(
            """
            SELECT
                date_trunc('minute', completed_at) AS minute,
                stage_name,
                COUNT(*) AS tasks_completed
            FROM tasks
            WHERE completed_at >= NOW() - INTERVAL '1 hour'
              AND status = 'COMPLETED'
            GROUP BY 1, 2
            ORDER BY 1
            """
        )
    return {
        "jobs_per_minute": [
            {"minute": r["minute"].isoformat(), "count": r["jobs_completed"]}
            for r in jobs_per_min
        ],
        "tasks_per_minute": [
            {
                "minute": r["minute"].isoformat(),
                "stage": r["stage_name"],
                "count": r["tasks_completed"],
            }
            for r in tasks_per_min
        ],
    }


@router.get("/api/metrics/failures")
async def failure_metrics(db: asyncpg.Pool = Depends(get_db)) -> dict:
    """Failure rates by stage over the last 24 hours."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                stage_name,
                COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
                COUNT(*) FILTER (WHERE status = 'FAILED') AS failed,
                AVG(retry_count) AS avg_retries,
                PERCENTILE_CONT(0.99) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000
                ) FILTER (WHERE status = 'COMPLETED') AS p99_latency_ms
            FROM tasks
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY stage_name
            ORDER BY stage_name
            """
        )
    return {
        "failure_rates": [
            {
                "stage": r["stage_name"],
                "completed": r["completed"],
                "failed": r["failed"],
                "failure_rate": round(
                    r["failed"] / max(r["completed"] + r["failed"], 1), 4
                ),
                "avg_retries": round(float(r["avg_retries"] or 0), 2),
                "p99_latency_ms": round(float(r["p99_latency_ms"] or 0), 1),
            }
            for r in rows
        ]
    }
