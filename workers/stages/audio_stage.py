"""
Audio Preprocessing Stage — adapted from Speech AI Pipeline Diagnostic.

Key changes vs. original:
  - MetricsRegistry singleton removed; metrics returned in result dict
  - StageMonitor context manager replaced with simple time.monotonic() timing
  - Function signature accepts raw input_data dict, returns result dict
  - result dict is stored as result_json in the tasks table
"""

from __future__ import annotations

import random
import time
from typing import Any

_HEALTHY_SNR_DB = 22.0
_HEALTHY_NOISE_FLOOR_DBFS = -60.0
_HEALTHY_LATENCY_MS_MEAN = 12.0


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process audio preprocessing task.

    input_data: {
        "audio_url": str | None,
        "duration_ms": float,
        "session_id": str | None,
    }

    Returns: {
        "snr_db": float,
        "noise_floor_dbfs": float,
        "duration_ms": float,
        "sample_rate": int,
        "channels": int,
        "latency_ms": float,
    }
    """
    start = time.monotonic()

    duration_ms = float(input_data.get("duration_ms", 1000.0))

    # Simulate microphone capture latency
    latency_ms = _HEALTHY_LATENCY_MS_MEAN + random.gauss(0, 2)
    latency_ms = max(1.0, latency_ms)
    time.sleep(latency_ms / 1000)

    # Simulate audio characteristics with realistic jitter
    snr_db = _HEALTHY_SNR_DB + random.gauss(0, 0.5)
    noise_floor_dbfs = _HEALTHY_NOISE_FLOOR_DBFS + random.gauss(0, 1.0)

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "snr_db": round(snr_db, 2),
        "noise_floor_dbfs": round(noise_floor_dbfs, 2),
        "duration_ms": duration_ms,
        "sample_rate": 16000,
        "channels": 1,
        "latency_ms": round(elapsed_ms, 2),
    }
