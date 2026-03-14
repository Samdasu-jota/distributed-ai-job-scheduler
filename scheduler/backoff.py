"""
Exponential backoff tracker for task retries.

Workers reset a task to PENDING on failure; the scheduler checks this
module before re-enqueuing to enforce a delay between attempts.
"""

from __future__ import annotations

import time
from typing import Optional
from uuid import UUID


class BackoffTracker:
    """
    Tracks next-eligible-at timestamps for tasks with retry_count > 0.

    Delay formula: min(2^retry_count, 60) seconds.
    """

    def __init__(self) -> None:
        self._next_eligible: dict[str, float] = {}  # task_id → unix timestamp

    def is_eligible(self, task_id: UUID, retry_count: int) -> bool:
        """Return True if the task is eligible for re-enqueue."""
        if retry_count == 0:
            return True
        key = str(task_id)
        eligible_at = self._next_eligible.get(key)
        if eligible_at is None:
            # First time we see this retry — set the backoff window
            delay = min(2 ** retry_count, 60)
            self._next_eligible[key] = time.monotonic() + delay
            return False
        return time.monotonic() >= eligible_at

    def mark_completed(self, task_id: UUID) -> None:
        """Remove backoff entry when task is successfully enqueued."""
        self._next_eligible.pop(str(task_id), None)

    def cleanup(self, max_age_seconds: float = 300.0) -> None:
        """Periodically evict stale entries to prevent unbounded growth."""
        now = time.monotonic()
        stale = [k for k, v in self._next_eligible.items() if now - v > max_age_seconds]
        for k in stale:
            del self._next_eligible[k]
