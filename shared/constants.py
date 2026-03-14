"""
Shared constants: DAG structure, stream mapping, status enums, stage ordering.

This module encodes the entire task dependency graph. Changing the pipeline
topology means updating STAGE_DAG here — no worker code changes needed.
"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ENQUEUED = "ENQUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkerStatus(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    DEAD = "DEAD"


# ── DAG Definition ─────────────────────────────────────────────────────────────
# Each stage lists the stage names that must be COMPLETED before it can run.
# At job-creation time, stage names are resolved to actual task UUIDs in the DB.
STAGE_DAG: dict[str, list[str]] = {
    "audio_preprocessing":  [],
    "speech_to_text":       ["audio_preprocessing"],
    "nlp_processing":       ["speech_to_text"],           # parallel branch A
    "grammar_correction":   ["speech_to_text"],           # parallel branch B
    "natural_phrasing":     ["grammar_correction"],
    "diagnostics":          ["nlp_processing", "natural_phrasing"],  # fan-in
    "aggregation":          ["diagnostics"],
}

# Ordered list of all stages — used when creating tasks for a new job
ALL_STAGES: list[str] = [
    "audio_preprocessing",
    "speech_to_text",
    "nlp_processing",
    "grammar_correction",
    "natural_phrasing",
    "diagnostics",
    "aggregation",
]

# Maps stage_name → Redis stream name
# nlp_processing and grammar_correction share the nlp stream so both can be
# consumed by the same pool of NLP worker containers (competing consumers).
STAGE_TO_STREAM: dict[str, str] = {
    "audio_preprocessing": "stream:tasks:audio",
    "speech_to_text":      "stream:tasks:stt",
    "nlp_processing":      "stream:tasks:nlp",
    "grammar_correction":  "stream:tasks:nlp",      # same stream → shared worker pool
    "natural_phrasing":    "stream:tasks:llm",
    "diagnostics":         "stream:tasks:diagnostics",
    "aggregation":         "stream:tasks:aggregation",
}

DEAD_LETTER_STREAM = "stream:tasks:dead"
CONSUMER_GROUP = "workers"

# All unique stream names (for consumer group initialization)
ALL_STREAMS: list[str] = list(dict.fromkeys(STAGE_TO_STREAM.values()))

# Max retries per stage — LLM stages limited because they are expensive
MAX_RETRIES_BY_STAGE: dict[str, int] = {
    "audio_preprocessing": 3,
    "speech_to_text":      3,
    "nlp_processing":      3,
    "grammar_correction":  3,
    "natural_phrasing":    2,
    "diagnostics":         3,
    "aggregation":         5,
}
