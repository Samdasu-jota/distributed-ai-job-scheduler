"""
Grammar Correction Stage — new stage split from llm_stage.py.

Runs in PARALLEL with nlp_processing (both depend only on speech_to_text).
Focuses on identifying and correcting grammatical errors using the LLM.
Result feeds into natural_phrasing stage.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

_BACKEND = os.getenv("PIPELINE_LLM_BACKEND", "mock")
_HEALTHY_LATENCY_MEAN_MS = 800.0

# Common grammar corrections for mock mode
_GRAMMAR_CORRECTIONS = {
    "She don't know how to speak English very well.":
        "She doesn't know how to speak English very well.",
    "Yesterday I have gone to the store and buyed some food.":
        "Yesterday I went to the store and bought some food.",
    "He is very good at speaking, isn't he?":
        "He is very good at speaking, isn't he?",  # Already correct
    "Can you help me understand this grammar rule?":
        "Can you help me understand this grammar rule?",  # Already correct
    "I would like to practice my English pronunciation.":
        "I would like to practice my English pronunciation.",  # Already correct
    "The quick brown fox jumps over the lazy dog.":
        "The quick brown fox jumps over the lazy dog.",  # Already correct
}

_CORRECTION_LABELS = [
    "Subject-verb agreement",
    "Irregular verb form",
    "Tense consistency",
    "Article usage",
    "Preposition choice",
]


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """
    Grammar correction task.

    input_data: result_json from speech_to_text task.

    Returns: {
        "original_text": str,
        "corrected_text": str,
        "corrections_made": list[str],
        "correction_count": int,
        "latency_ms": float,
        "backend": str,
    }
    """
    transcript = input_data.get("transcript", "")

    if _BACKEND == "claude":
        return _call_claude(transcript)
    else:
        return _mock_correct(transcript)


def _mock_correct(transcript: str) -> dict[str, Any]:
    start = time.monotonic()

    latency_ms = _HEALTHY_LATENCY_MEAN_MS + random.gauss(0, 80)
    latency_ms = max(100.0, latency_ms)
    time.sleep(latency_ms / 1000)

    corrected = _GRAMMAR_CORRECTIONS.get(
        transcript,
        transcript + " [Grammar verified — no structural errors found.]",
    )

    # Determine what was corrected (heuristic for mock)
    corrections_made: list[str] = []
    if corrected != transcript:
        # Pick a plausible correction label
        corrections_made.append(random.choice(_CORRECTION_LABELS))

    elapsed_ms = (time.monotonic() - start) * 1000

    return {
        "original_text": transcript,
        "corrected_text": corrected,
        "corrections_made": corrections_made,
        "correction_count": len(corrections_made),
        "latency_ms": round(elapsed_ms, 2),
        "backend": "mock",
    }


def _call_claude(transcript: str) -> dict[str, Any]:
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
                    "Correct any grammatical errors in the following English sentence. "
                    "Return a JSON object with keys: corrected_text (string), "
                    "corrections_made (list of strings describing each correction). "
                    "If no corrections needed, return the original text unchanged.\n\n"
                    f"Sentence: {transcript}"
                ),
            }
        ],
    )

    latency_ms = (time.monotonic() - start) * 1000
    raw = message.content[0].text if message.content else "{}"

    try:
        import json
        result = json.loads(raw)
        corrected = result.get("corrected_text", transcript)
        corrections = result.get("corrections_made", [])
    except Exception:
        corrected = transcript
        corrections = []

    return {
        "original_text": transcript,
        "corrected_text": corrected,
        "corrections_made": corrections,
        "correction_count": len(corrections),
        "latency_ms": round(latency_ms, 2),
        "backend": "claude",
    }
