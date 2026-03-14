"""
WebSocket connection manager — adapted from Speech AI Pipeline Diagnostic.

Manages per-job and dashboard broadcast channels. Clients subscribe to:
  - /ws/jobs/{job_id}   → task-level state updates for a single job
  - /ws/dashboard       → aggregate queue depths, worker counts, throughput
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # job_id → list of websockets watching that job
        self._job_sockets: dict[str, list[WebSocket]] = defaultdict(list)
        # dashboard broadcast sockets
        self._dashboard_sockets: list[WebSocket] = []

    # ── Job-level subscriptions ───────────────────────────────────────────────

    async def connect_job(self, ws: WebSocket, job_id: str) -> None:
        await ws.accept()
        self._job_sockets[job_id].append(ws)
        logger.info("ws_job_connected", extra={"job_id": job_id})

    def disconnect_job(self, ws: WebSocket, job_id: str) -> None:
        if ws in self._job_sockets[job_id]:
            self._job_sockets[job_id].remove(ws)

    async def broadcast_job_update(self, job_id: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": "job_update", "data": data})
        dead: list[WebSocket] = []
        for ws in list(self._job_sockets.get(job_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._job_sockets[job_id].remove(ws)

    # ── Dashboard broadcast ───────────────────────────────────────────────────

    async def connect_dashboard(self, ws: WebSocket) -> None:
        await ws.accept()
        self._dashboard_sockets.append(ws)
        logger.info("ws_dashboard_connected", extra={"total": len(self._dashboard_sockets)})

    def disconnect_dashboard(self, ws: WebSocket) -> None:
        if ws in self._dashboard_sockets:
            self._dashboard_sockets.remove(ws)

    async def broadcast_dashboard(self, data: dict[str, Any]) -> None:
        payload = json.dumps({"type": "dashboard_update", "data": data})
        dead: list[WebSocket] = []
        for ws in list(self._dashboard_sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._dashboard_sockets.remove(ws)

    @property
    def active_connections(self) -> int:
        job_count = sum(len(v) for v in self._job_sockets.values())
        return job_count + len(self._dashboard_sockets)


# Module-level singleton imported by routes and background tasks
manager = ConnectionManager()
