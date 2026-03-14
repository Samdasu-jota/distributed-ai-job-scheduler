"""
Prometheus metrics registry for the distributed scheduler.

Each process (api, scheduler, workers) imports this module and gets a
consistent set of instruments. Workers expose /metrics on their own port;
the API gateway exposes the global /metrics endpoint.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Use the default registry so prometheus_client's built-in process metrics
# are also exposed alongside our custom instruments.
from prometheus_client import REGISTRY as _registry


# ── Scheduler metrics ─────────────────────────────────────────────────────────
scheduler_enqueue_total = Counter(
    "scheduler_enqueue_total",
    "Total tasks enqueued by the scheduler",
    ["stage"],
)

scheduler_cycle_duration_seconds = Histogram(
    "scheduler_cycle_duration_seconds",
    "Scheduler DAG resolution cycle duration",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

scheduler_ready_tasks_per_cycle = Histogram(
    "scheduler_ready_tasks_per_cycle",
    "Number of ready tasks found per scheduler cycle",
    buckets=[0, 1, 5, 10, 25, 50, 100],
)

# ── Worker metrics ────────────────────────────────────────────────────────────
worker_task_total = Counter(
    "worker_task_total",
    "Total tasks processed by workers",
    ["worker_type", "stage", "status"],   # status: completed | failed | retried
)

task_duration_seconds = Histogram(
    "task_duration_seconds",
    "Task execution duration by stage",
    ["stage"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── Job metrics ───────────────────────────────────────────────────────────────
job_total = Counter(
    "job_total",
    "Total jobs by final status",
    ["status"],   # completed | failed | cancelled
)

job_e2e_duration_seconds = Histogram(
    "job_e2e_duration_seconds",
    "End-to-end job duration from submission to completion",
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# ── Queue metrics (gauges, scraped by Prometheus) ─────────────────────────────
queue_depth_pending = Gauge(
    "queue_depth_pending",
    "Number of pending messages in each Redis task stream",
    ["stream"],
)

active_jobs_count = Gauge(
    "active_jobs_count",
    "Number of currently RUNNING jobs",
)

worker_count = Gauge(
    "worker_count",
    "Number of workers by type and status",
    ["worker_type", "status"],
)

# ── Per-stage pipeline metrics (reused from existing project) ─────────────────
audio_capture_latency_ms = Histogram(
    "audio_capture_latency_ms",
    "Audio preprocessing latency",
    buckets=[5, 10, 20, 50, 100, 200],
)

stt_latency_ms = Histogram(
    "stt_latency_ms",
    "STT transcription latency",
    buckets=[50, 100, 200, 500, 1000, 2000, 5000],
)

llm_latency_ms = Histogram(
    "llm_latency_ms",
    "LLM API call latency",
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000],
)

stt_word_error_rate = Gauge("stt_word_error_rate", "Current STT word error rate")
audio_snr_db = Gauge("audio_snr_db", "Current audio SNR in dB")
