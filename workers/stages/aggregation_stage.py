"""
Aggregation Stage — final stage, adapted from output_stage.py.

Collects results from all upstream stages and assembles the complete
tutoring session report. This is the terminal node of the DAG.
"""

from __future__ import annotations

import random
import time
from typing import Any

_HEALTHY_LATENCY_MEAN_MS = 8.0


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Aggregate all stage results into a final tutoring session report.

    input_data: merged dict from all upstream task results — contains
        everything from audio, STT, NLP, grammar, phrasing, and diagnostics stages.

    Returns: {
        "session_report": dict,
        "overall_score": float,
        "recommendations": list[str],
        "latency_ms": float,
    }
    """
    start = time.monotonic()

    latency_ms = _HEALTHY_LATENCY_MEAN_MS + random.gauss(0, 2)
    latency_ms = max(1.0, latency_ms)
    time.sleep(latency_ms / 1000)

    # Pull key results from upstream stages
    original_transcript = input_data.get("transcript", "")
    corrected_text = input_data.get("corrected_text", original_transcript)
    phrasing_suggestions = input_data.get("phrasing_suggestions", [])
    grammar_hints = input_data.get("grammar_hints", [])
    corrections_made = input_data.get("corrections_made", [])
    fluency_score = float(input_data.get("fluency_score", 0.85))
    word_error_rate = float(input_data.get("word_error_rate", 0.06))
    pipeline_status = input_data.get("pipeline_status", "HEALTHY")
    active_alerts = input_data.get("active_alerts", [])
    stage_health = input_data.get("stage_health", {})
    snr_db = float(input_data.get("snr_db", 22.0))

    # Compute overall session score (0.0 – 10.0)
    # Weighted average of fluency, WER (inverted), and grammar quality
    fluency_component = fluency_score * 4.0                         # 0–4 points
    accuracy_component = max(0.0, (1.0 - word_error_rate)) * 3.0   # 0–3 points
    grammar_component = max(0.0, 3.0 - len(corrections_made))       # 0–3 points
    overall_score = round(fluency_component + accuracy_component + grammar_component, 1)
    overall_score = max(0.0, min(10.0, overall_score))

    # Generate recommendations
    recommendations: list[str] = []
    if word_error_rate > 0.15:
        recommendations.append("Practice speaking more slowly and clearly to improve transcription accuracy.")
    if fluency_score < 0.7:
        recommendations.extend(phrasing_suggestions[:2])
    if corrections_made:
        recommendations.append(f"Review: {', '.join(corrections_made[:2])}")
    if grammar_hints:
        recommendations.extend(grammar_hints[:2])
    if not recommendations:
        recommendations.append("Excellent! Your English sounds natural and grammatically correct.")

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "session_report": {
            "original_transcript": original_transcript,
            "corrected_text": corrected_text,
            "corrections_made": corrections_made,
            "phrasing_suggestions": phrasing_suggestions,
            "grammar_hints": grammar_hints,
            "pipeline_status": pipeline_status,
            "stage_health": stage_health,
            "active_alerts_count": len(active_alerts),
            "audio_quality_db": snr_db,
        },
        "overall_score": overall_score,
        "fluency_score": fluency_score,
        "word_error_rate": word_error_rate,
        "recommendations": recommendations[:5],  # cap at 5
        "latency_ms": round(elapsed_ms, 2),
    }
