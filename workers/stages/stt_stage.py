"""
Speech-to-Text Stage — adapted from Speech AI Pipeline Diagnostic.

Receives audio metadata from the audio_preprocessing task's result_json.
Returns transcript and quality metrics as a plain dict for PostgreSQL storage.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

_BACKEND = os.getenv("PIPELINE_STT_BACKEND", "mock")

_HEALTHY_WER = 0.06
_HEALTHY_CONFIDENCE = 0.88
_HEALTHY_LATENCY_MEAN_MS = 320.0

_SAMPLE_TRANSCRIPTS = [
    "The quick brown fox jumps over the lazy dog.",
    "Can you help me understand this grammar rule?",
    "I would like to practice my English pronunciation.",
    "Please correct my sentence if it is wrong.",
    "How do I use the present perfect tense correctly?",
    "She don't know how to speak English very well.",
    "Yesterday I have gone to the store and buyed some food.",
    "He is very good at speaking, isn't he?",
]


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process speech-to-text task.

    input_data: result_json from audio_preprocessing task — contains
        snr_db, noise_floor_dbfs, duration_ms, sample_rate, channels.

    Returns: {
        "transcript": str,
        "confidence": float,
        "word_error_rate": float,
        "latency_ms": float,
        "backend": str,
        "words": list[str],
    }
    """
    snr_db = float(input_data.get("snr_db", 22.0))

    if _BACKEND == "mock":
        return _mock_transcribe(snr_db)
    else:
        return _mock_transcribe(snr_db)  # Real backends are plugged in here


def _mock_transcribe(snr_db: float) -> dict[str, Any]:
    start = time.monotonic()

    # Derive WER from SNR — low SNR means poor audio, high WER
    # Map: SNR 22dB→WER 6%, SNR 10dB→WER ~20%, SNR 5dB→WER ~35%
    snr_penalty = max(0.0, (22.0 - snr_db) / 100.0)
    wer = _HEALTHY_WER + snr_penalty + random.gauss(0, 0.01)
    wer = max(0.0, min(1.0, wer))

    # Confidence inversely correlated with WER
    confidence = max(0.1, _HEALTHY_CONFIDENCE - wer * 3.0 + random.gauss(0, 0.02))

    # Simulate transcription latency (degrades with noise)
    noise_factor = max(1.0, (22.0 - snr_db) * 0.05)
    latency_ms = _HEALTHY_LATENCY_MEAN_MS * (1 + noise_factor) + random.gauss(0, 30)
    latency_ms = max(50.0, latency_ms)
    time.sleep(latency_ms / 1000)

    # Choose transcript; mangle words if WER is very high
    transcript = random.choice(_SAMPLE_TRANSCRIPTS)
    if wer > 0.25:
        words = transcript.split()
        n_corrupt = int(len(words) * wer)
        for i in random.sample(range(len(words)), min(n_corrupt, len(words))):
            words[i] = "???"
        transcript = " ".join(words)

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "transcript": transcript,
        "confidence": round(confidence, 3),
        "word_error_rate": round(wer, 4),
        "latency_ms": round(elapsed_ms, 2),
        "backend": _BACKEND,
        "words": transcript.split(),
        "snr_db_used": round(snr_db, 2),
    }
