# Distributed AI Job Scheduler for English Tutoring Diagnostics

> A distributed compute platform that processes English tutoring AI workloads across multiple worker nodes — demonstrating the engineering principles behind real build infrastructure and job scheduling systems.

## Architecture

```
  HTTP Client ──► API Gateway (FastAPI :8000)
                        │
                        ▼
              PostgreSQL (:5432) ◄──► Redis Streams (:6379)
                jobs, tasks,           One stream per stage type
                workers tables         Consumer groups (XREADGROUP)
                                       Dead-letter stream
                        ▲                    ▲
                        │                    │
              ┌──────────────┐   ┌───────────────────────┐
              │  Scheduler   │──►│     Worker Pool        │
              │  (poll 2s)   │   │  worker_audio   (x1)  │
              │  DAG resolver│   │  worker_stt     (x1)  │
              │  Enqueues to │   │  worker_nlp     (x2)  │
              │  Redis       │   │  worker_llm     (x2)  │
              └──────────────┘   │  worker_diag    (x1)  │
                                 │  worker_agg     (x1)  │
                                 └───────────────────────┘
              Prometheus (:9090) + Grafana (:3001)
              Next.js Dashboard  (:3000)
```

## Task DAG (7 stages)

```
audio_preprocessing (stage 1)
    └── speech_to_text (stage 2)
            ├── nlp_processing (stage 3a) ──────────────┐
            └── grammar_correction (stage 3b)            │
                        └── natural_phrasing (stage 4) ──┤
                                                         ▼
                                                  diagnostics (stage 5)  ← fan-in
                                                         └── aggregation (stage 6)
```

**Key distributed systems patterns demonstrated:**
- DAG-aware scheduling with fan-out/fan-in
- Redis Streams consumer groups (exactly-once delivery)
- Optimistic locking (`UPDATE WHERE status='PENDING'`) for idempotent task enqueue
- Dead-letter routing for exhausted retries
- Exponential backoff for failed tasks
- Dead worker detection + task reclaim via `XCLAIM`

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API Gateway | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin/admin) |

## Submit a Job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student-1", "duration_ms": 1000, "priority": 3}'
```

Response includes `job_id`. Then poll status:

```bash
curl http://localhost:8000/api/jobs/<job_id>
```

Or watch the Task DAG update live in the dashboard at http://localhost:3000.

## Key API Endpoints

```
POST   /api/jobs              Submit job → creates 7 tasks with DAG depends_on
GET    /api/jobs/{id}         Job status + all task states
GET    /api/jobs/{id}/dag     DAG visualization data (nodes + edges)
DELETE /api/jobs/{id}         Cancel job
GET    /api/workers           All registered workers
GET    /api/queues            Redis stream depths per stage
GET    /api/metrics/throughput  Jobs/min time series
GET    /metrics               Prometheus exposition
WS     /api/jobs/ws/jobs/{id} Live task updates
WS     /api/jobs/ws/dashboard  Live queue + worker counts
```

## Project Structure

```
├── api/            FastAPI gateway
├── scheduler/      DAG-aware scheduler process
├── workers/        Stage workers + base worker class
│   └── stages/     Pipeline stage logic (ported from Speech AI Pipeline Diagnostic)
├── shared/         Shared constants, DB/Redis clients, Prometheus metrics
├── migrations/     Alembic PostgreSQL migrations
├── frontend/       Next.js + ReactFlow dashboard
└── observability/  Prometheus + Grafana config
```

## Tradeoffs

| Decision | Choice | Reason |
|---|---|---|
| Redis Streams vs Kafka | Redis Streams | Consumer groups = exactly-once; no JVM; PEL for crash recovery |
| Polling vs LISTEN/NOTIFY | Polling (2s) | Batches tasks; simpler; 2s lag imperceptible for tutoring |
| DAG Scheduler vs Celery | Custom DAG | Celery chains can't express fan-in (diagnostics depends on 2 parallel branches) |
| Docker Compose vs K8s | Docker Compose | Workers are stateless → K8s-ready; HPA is a migration not a rewrite |

## Tech Stack

- **Python 3.12** — API gateway, scheduler, workers
- **FastAPI** — async REST + WebSocket server
- **asyncpg** — high-performance async PostgreSQL driver
- **redis.asyncio** — async Redis Streams (XREADGROUP, XCLAIM, XACK)
- **PostgreSQL 16** — job/task state machine, results storage
- **Alembic** — database migrations
- **Next.js 14** — React dashboard
- **ReactFlow** — live DAG visualization
- **Recharts** — throughput + queue depth charts
- **Prometheus** — metrics collection
- **Grafana** — time-series dashboards
- **Docker Compose** — multi-service orchestration (8+ containers)

## Built On

This project is built on top of the [Speech AI Pipeline Diagnostic](../Speech%20AI%20Pipeline%20Diagnostic) project, which provided the pipeline stage implementations (audio, STT, NLP, LLM, output). Those stages were decomposed from a monolithic sequential runner into independently deployable worker tasks.
