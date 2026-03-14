"""
NLP Processing Stage — adapted from Speech AI Pipeline Diagnostic.

This stage runs in PARALLEL with grammar_correction (both depend only on
speech_to_text). It performs lightweight linguistic analysis on the transcript.
"""

from __future__ import annotations

import random
import time
from typing import Any

_HEALTHY_LATENCY_MEAN_MS = 25.0


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process NLP analysis task.

    input_data: result_json from speech_to_text task.

    Returns: {
        "original_text": str,
        "token_count": int,
        "has_grammar_errors": bool,
        "grammar_hints": list[str],
        "sentence_structure": str,
        "latency_ms": float,
    }
    """
    start = time.monotonic()

    transcript = input_data.get("transcript", "")

    latency_ms = _HEALTHY_LATENCY_MEAN_MS + random.gauss(0, 5)
    latency_ms = max(5.0, latency_ms)
    time.sleep(latency_ms / 1000)

    tokens = transcript.split()
    token_count = len(tokens)

    # Heuristic grammar hints (same logic as original nlp_stage.py)
    hints: list[str] = []
    if transcript and not transcript.strip().endswith((".","?","!")):
        hints.append("Sentence may be missing terminal punctuation.")
    if transcript and not transcript[0].isupper():
        hints.append("Sentence should begin with a capital letter.")

    # Additional heuristics for common ESL errors
    text_lower = transcript.lower()
    if " don't " in text_lower or " doesn't " in text_lower:
        if any(p in text_lower for p in [" he don't", " she don't", " it don't"]):
            hints.append("Subject-verb agreement error detected (he/she/it + don't).")
    if " buyed" in text_lower or " thinked" in text_lower:
        hints.append("Possible irregular past tense error.")
    if " have went" in text_lower or " have went" in text_lower:
        hints.append("Possible past participle error (use 'have gone').")

    # Rough sentence structure classification
    if token_count < 5:
        structure = "fragment"
    elif token_count < 15:
        structure = "simple"
    else:
        structure = "complex"

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "original_text": transcript,
        "token_count": token_count,
        "has_grammar_errors": len(hints) > 0,
        "grammar_hints": hints,
        "sentence_structure": structure,
        "word_error_rate": input_data.get("word_error_rate", 0.06),
        "latency_ms": round(elapsed_ms, 2),
    }
