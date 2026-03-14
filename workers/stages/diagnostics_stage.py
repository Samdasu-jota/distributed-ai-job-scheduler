"""
Diagnostics Stage — fan-in worker.

This is the most architecturally interesting stage: it WAITS for BOTH
nlp_processing AND natural_phrasing to complete before it can run
(fan-in dependency). The scheduler enforces this via the depends_on array.

Adapted from diagnostics/engine.py + diagnostics/root_cause_analyzer.py
in the original Speech AI Pipeline Diagnostic project.
"""

from __future__ import annotations

import random
import time
from typing import Any

from workers.stages.rules import RULES, RuleResult, Severity


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Run diagnostic analysis on the combined NLP + phrasing results.

    input_data: merged dict from both upstream tasks:
        From nlp_processing: token_count, has_grammar_errors, grammar_hints,
                             sentence_structure, word_error_rate
        From natural_phrasing: fluency_score, phrasing_suggestions, corrected_text
        From audio_preprocessing (passed through): snr_db
        From grammar_correction: correction_count

    Returns: {
        "pipeline_status": str,   # HEALTHY | DEGRADED | CRITICAL
        "active_alerts": list[dict],
        "root_cause": dict | None,
        "stage_health": dict[str, str],
        "metrics_snapshot": dict[str, float],
        "latency_ms": float,
    }
    """
    start = time.monotonic()

    # Simulate a short analysis delay
    time.sleep(random.uniform(0.05, 0.15))

    # Build a metrics snapshot from upstream task results
    snapshot: dict[str, float] = {
        "word_error_rate": float(input_data.get("word_error_rate", 0.06)),
        "snr_db": float(input_data.get("snr_db", 22.0)),
        "fluency_score": float(input_data.get("fluency_score", 0.85)),
        "correction_count": float(input_data.get("correction_count", 0)),
        "token_count": float(input_data.get("token_count", 10)),
    }

    # Evaluate DTC rules
    results: list[RuleResult] = [rule.evaluate(snapshot) for rule in RULES]
    triggered = [r for r in results if r.triggered]

    # Determine pipeline health
    if any(r.severity == Severity.CRITICAL for r in triggered):
        pipeline_status = "CRITICAL"
    elif triggered:
        pipeline_status = "DEGRADED"
    else:
        pipeline_status = "HEALTHY"

    # Simple root-cause analysis
    root_cause = _analyze_root_cause(triggered, snapshot)

    # Stage health map
    stage_health = {
        "audio_preprocessing": "CRITICAL" if snapshot["snr_db"] < 5.0 else
                                "DEGRADED" if snapshot["snr_db"] < 10.0 else "HEALTHY",
        "speech_to_text": "CRITICAL" if snapshot["word_error_rate"] > 0.20 else
                          "DEGRADED" if snapshot["word_error_rate"] > 0.15 else "HEALTHY",
        "nlp_processing": "DEGRADED" if input_data.get("has_grammar_errors") else "HEALTHY",
        "grammar_correction": "DEGRADED" if snapshot["correction_count"] >= 3 else "HEALTHY",
        "natural_phrasing": "CRITICAL" if snapshot["fluency_score"] < 0.5 else
                            "DEGRADED" if snapshot["fluency_score"] < 0.7 else "HEALTHY",
        "diagnostics": "HEALTHY",
    }

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "pipeline_status": pipeline_status,
        "active_alerts": [
            {
                "rule_id": r.rule_id,
                "dtc_code": r.dtc_code,
                "severity": r.severity,
                "message": r.message,
                "current_value": r.current_value,
                "baseline_value": r.baseline_value,
                "stage": r.stage,
            }
            for r in triggered
        ],
        "root_cause": root_cause,
        "stage_health": stage_health,
        "metrics_snapshot": snapshot,
        "latency_ms": round(elapsed_ms, 2),
    }


def _analyze_root_cause(
    triggered: list[RuleResult],
    snapshot: dict[str, float],
) -> dict[str, Any] | None:
    if not triggered:
        return None

    triggered_codes = {r.dtc_code for r in triggered}

    # RCA Rule 1: Low SNR causing high WER
    if "AUD-001" in triggered_codes and "STT-001" in triggered_codes:
        return {
            "probable_cause": "Microphone noise degrading transcription accuracy",
            "confidence": 0.91,
            "evidence": [
                f"AUD-001: Audio SNR dropped to {snapshot['snr_db']:.1f} dB (baseline 22 dB)",
                f"STT-001: WER increased to {snapshot['word_error_rate']*100:.1f}% (baseline 6%)",
            ],
            "suggested_fix": "Enable noise filtering or check microphone placement",
            "matched_rule": "RCA-01",
        }

    # RCA Rule 2: Low fluency with grammar errors
    if "NLP-001" in triggered_codes and "GRM-001" in triggered_codes:
        return {
            "probable_cause": "Multiple grammatical errors significantly impacting fluency",
            "confidence": 0.85,
            "evidence": [
                f"GRM-001: {int(snapshot['correction_count'])} grammar corrections required",
                f"NLP-001: Fluency score {snapshot['fluency_score']:.2f} (baseline 0.85)",
            ],
            "suggested_fix": "Focus on grammar fundamentals: verb tense and subject-verb agreement",
            "matched_rule": "RCA-02",
        }

    # Generic fallback: report most severe triggered rule
    most_severe = triggered[0]
    return {
        "probable_cause": most_severe.message,
        "confidence": 0.65,
        "evidence": [f"{most_severe.dtc_code}: {most_severe.message}"],
        "suggested_fix": "Review flagged metric and compare to baseline",
        "matched_rule": "RCA-GENERIC",
    }
