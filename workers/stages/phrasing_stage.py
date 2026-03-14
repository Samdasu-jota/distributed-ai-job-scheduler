"""
Natural Phrasing Stage — new stage split from llm_stage.py.

Depends on grammar_correction. Suggests more natural, idiomatic English
phrasings for the corrected text. Result feeds into diagnostics (fan-in).
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

_BACKEND = os.getenv("PIPELINE_LLM_BACKEND", "mock")
_HEALTHY_LATENCY_MEAN_MS = 900.0

_PHRASING_SUGGESTIONS = [
    "Consider using more active voice for clearer communication.",
    "This phrasing sounds natural. No changes needed.",
    "Try 'I'd like to' instead of 'I would like to' for a more conversational tone.",
    "Using contractions (e.g., 'don't' instead of 'do not') sounds more natural in speech.",
    "This is grammatically correct and sounds natural.",
    "Consider varying your sentence starters to sound more fluent.",
]


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Natural phrasing suggestion task.

    input_data: result_json from grammar_correction task.

    Returns: {
        "original_text": str,
        "corrected_text": str,
        "phrasing_suggestions": list[str],
        "fluency_score": float,  # 0.0–1.0
        "latency_ms": float,
        "backend": str,
    }
    """
    corrected_text = input_data.get("corrected_text", "")
    original_text = input_data.get("original_text", corrected_text)

    if _BACKEND == "claude":
        return _call_claude(corrected_text, original_text)
    else:
        return _mock_suggest(corrected_text, original_text)


def _mock_suggest(corrected_text: str, original_text: str) -> dict[str, Any]:
    start = time.monotonic()

    latency_ms = _HEALTHY_LATENCY_MEAN_MS + random.gauss(0, 100)
    latency_ms = max(100.0, latency_ms)
    time.sleep(latency_ms / 1000)

    # Generate 1–2 phrasing suggestions
    suggestions = random.sample(_PHRASING_SUGGESTIONS, min(2, len(_PHRASING_SUGGESTIONS)))

    # Mock fluency score: higher if no corrections were needed
    had_corrections = corrected_text != original_text
    fluency_score = random.uniform(0.55, 0.75) if had_corrections else random.uniform(0.82, 0.98)

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "original_text": original_text,
        "corrected_text": corrected_text,
        "phrasing_suggestions": suggestions,
        "fluency_score": round(fluency_score, 3),
        "latency_ms": round(elapsed_ms, 2),
        "backend": "mock",
    }


def _call_claude(corrected_text: str, original_text: str) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic()
    start = time.monotonic()

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    "Evaluate the following English sentence for naturalness and fluency. "
                    "Return a JSON object with: phrasing_suggestions (list of strings), "
                    "fluency_score (float 0–1). Be concise.\n\n"
                    f"Sentence: {corrected_text}"
                ),
            }
        ],
    )

    latency_ms = (time.monotonic() - start) * 1000
    raw = message.content[0].text if message.content else "{}"

    try:
        import json
        result = json.loads(raw)
        suggestions = result.get("phrasing_suggestions", [])
        fluency_score = float(result.get("fluency_score", 0.8))
    except Exception:
        suggestions = []
        fluency_score = 0.8

    return {
        "original_text": original_text,
        "corrected_text": corrected_text,
        "phrasing_suggestions": suggestions,
        "fluency_score": round(fluency_score, 3),
        "latency_ms": round(latency_ms, 2),
        "backend": "claude",
    }
