"""
API Gateway — FastAPI application entry point.

Lifecycle:
  startup  → create DB pool, init Redis consumer groups
  shutdown → close DB pool, close Redis connection
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import jobs, workers, queues
from api.routes.metrics_route import router as metrics_router
from api.websocket.manager import manager
from shared.db import close_pool, create_pool
from shared.redis_client import close_redis, get_redis, init_consumer_groups

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("api_startup")
    await create_pool()
    await get_redis()
    await init_consumer_groups()
    # Start background dashboard broadcast task
    broadcast_task = asyncio.create_task(_dashboard_broadcast_loop())
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    broadcast_task.cancel()
    await close_pool()
    await close_redis()
    logger.info("api_shutdown")


async def _dashboard_broadcast_loop() -> None:
    """
    Every 3 seconds, broadcast queue depths and worker counts to all dashboard
    WebSocket clients so the frontend stays live without polling.
    """
    from shared.constants import ALL_STREAMS, CONSUMER_GROUP
    from shared.redis_client import get_redis as _redis
    from shared.db import get_pool as _pool

    while True:
        try:
            await asyncio.sleep(3)
            redis = await _redis()
            db = await _pool()

            queue_data = {}
            for stream in ALL_STREAMS:
                try:
                    length = await redis.xlen(stream)
                    queue_data[stream] = length
                except Exception:
                    queue_data[stream] = 0

            async with db.acquire() as conn:
                worker_rows = await conn.fetch(
                    "SELECT worker_type, status, COUNT(*) AS cnt FROM workers GROUP BY worker_type, status"
                )
                job_counts = await conn.fetchrow(
                    "SELECT COUNT(*) FILTER (WHERE status='RUNNING') AS running, "
                    "COUNT(*) FILTER (WHERE status='PENDING') AS pending "
                    "FROM jobs"
                )

            workers_summary = {}
            for row in worker_rows:
                key = f"{row['worker_type']}:{row['status']}"
                workers_summary[key] = row["cnt"]

            await manager.broadcast_dashboard({
                "queues": queue_data,
                "workers": workers_summary,
                "active_jobs": job_counts["running"],
                "pending_jobs": job_counts["pending"],
            })
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("dashboard_broadcast_error", extra={"error": str(exc)})


app = FastAPI(
    title="Distributed AI Job Scheduler",
    description="DAG-aware distributed job scheduler for English tutoring AI workloads",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(workers.router)
app.include_router(queues.router)
app.include_router(metrics_router)

# Re-register WebSocket routes from the jobs router at top level
# (they are already included via jobs.router — this is just documentation)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "api-gateway"}
