"""Pydantic request/response schemas for the jobs API."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobSubmitRequest(BaseModel):
    user_id: Optional[str] = None
    audio_url: Optional[str] = None
    duration_ms: Optional[float] = Field(default=1000.0, ge=100, le=300_000)
    session_id: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)


class TaskStatusResponse(BaseModel):
    task_id: str
    stage_name: str
    status: str
    depends_on: list[str]
    enqueued_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    worker_id: Optional[str]
    retry_count: int
    error: Optional[str]


class JobResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    user_id: Optional[str]
    priority: int
    tasks: list[TaskStatusResponse] = []


class DAGNode(BaseModel):
    id: str
    stage_name: str
    status: str
    depends_on: list[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    worker_id: Optional[str]
    retry_count: int


class DAGEdge(BaseModel):
    source: str   # task_id of upstream task
    target: str   # task_id of downstream task


class DAGResponse(BaseModel):
    job_id: str
    nodes: list[DAGNode]
    edges: list[DAGEdge]


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
