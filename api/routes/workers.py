"""Worker management routes."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from shared.db import get_pool

router = APIRouter(prefix="/api/workers", tags=["workers"])


async def get_db() -> asyncpg.Pool:
    return await get_pool()


@router.get("")
async def list_workers(db: asyncpg.Pool = Depends(get_db)) -> dict:
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM workers ORDER BY worker_type, registered_at"
        )
    return {
        "workers": [
            {
                "id": str(r["id"]),
                "hostname": r["hostname"],
                "worker_type": r["worker_type"],
                "status": r["status"],
                "last_heartbeat": r["last_heartbeat"].isoformat(),
                "tasks_completed": r["tasks_completed"],
                "tasks_failed": r["tasks_failed"],
                "current_task_id": str(r["current_task_id"]) if r["current_task_id"] else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.delete("/{worker_id}")
async def deregister_worker(worker_id: str, db: asyncpg.Pool = Depends(get_db)) -> dict:
    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE workers SET status='DEAD' WHERE id=$1",
            UUID(worker_id),
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Worker not found")
    return {"worker_id": worker_id, "status": "DEAD"}
