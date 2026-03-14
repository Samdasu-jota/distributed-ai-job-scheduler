"""
Shared dataclasses mirroring the PostgreSQL schema.

These are plain Python dataclasses — no ORM overhead. asyncpg returns
asyncpg.Record objects which we convert to these for type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from shared.constants import JobStatus, TaskStatus, WorkerStatus


@dataclass
class Job:
    id: UUID
    status: JobStatus
    submitted_at: datetime
    input_data: dict[str, Any]
    priority: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "priority": self.priority,
            "error": self.error,
        }


@dataclass
class Task:
    id: UUID
    job_id: UUID
    stage_name: str
    status: TaskStatus
    depends_on: list[UUID] = field(default_factory=list)
    enqueued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[UUID] = None
    result_json: Optional[dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    stream_message_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "job_id": str(self.job_id),
            "stage_name": self.stage_name,
            "status": self.status,
            "depends_on": [str(d) for d in self.depends_on],
            "enqueued_at": self.enqueued_at.isoformat() if self.enqueued_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "worker_id": str(self.worker_id) if self.worker_id else None,
            "retry_count": self.retry_count,
            "error": self.error,
        }


@dataclass
class Worker:
    id: UUID
    hostname: str
    worker_type: str
    status: WorkerStatus
    last_heartbeat: datetime
    registered_at: datetime
    tasks_completed: int = 0
    tasks_failed: int = 0
    current_task_id: Optional[UUID] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "hostname": self.hostname,
            "worker_type": self.worker_type,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "registered_at": self.registered_at.isoformat(),
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "current_task_id": str(self.current_task_id) if self.current_task_id else None,
        }
