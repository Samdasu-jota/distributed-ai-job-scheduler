"""
Diagnostic rules — copied verbatim from Speech AI Pipeline Diagnostic.

DTC-style fault codes adapted for the distributed scheduler context.
Evaluated inside the diagnostics_stage worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


@dataclass
class RuleResult:
    rule_id: str
    dtc_code: str
    triggered: bool
    severity: Severity
    message: str
    current_value: float
    baseline_value: Optional[float] = None
    stage: str = "unknown"


@dataclass
class Rule:
    rule_id: str
    dtc_code: str
    stage: str
    metric: str
    condition: Callable[[float], bool]
    severity: Severity
    message: str
    baseline: Optional[float] = None

    def evaluate(self, snapshot: dict[str, float]) -> RuleResult:
        value = snapshot.get(self.metric, 0.0)
        triggered = self.condition(value)
        return RuleResult(
            rule_id=self.rule_id,
            dtc_code=self.dtc_code,
            triggered=triggered,
            severity=self.severity,
            message=self.message,
            current_value=value,
            baseline_value=self.baseline,
            stage=self.stage,
        )


RULES: list[Rule] = [
    Rule(
        rule_id="STT_HIGH_WER",
        dtc_code="STT-001",
        stage="speech_to_text",
        metric="word_error_rate",
        condition=lambda v: v > 0.20,
        severity=Severity.CRITICAL,
        message="STT Word Error Rate exceeded 20% — transcription severely degraded",
        baseline=0.06,
    ),
    Rule(
        rule_id="STT_LOW_CONFIDENCE",
        dtc_code="STT-002",
        stage="speech_to_text",
        metric="word_error_rate",
        condition=lambda v: v > 0.15,
        severity=Severity.WARN,
        message="STT confidence scores falling — possible audio quality issue",
        baseline=0.06,
    ),
    Rule(
        rule_id="LOW_AUDIO_SNR",
        dtc_code="AUD-001",
        stage="audio_capture",
        metric="snr_db",
        condition=lambda v: v < 10.0,
        severity=Severity.WARN,
        message="Audio SNR below 10 dB — background noise likely affecting quality",
        baseline=22.0,
    ),
    Rule(
        rule_id="LOW_FLUENCY",
        dtc_code="NLP-001",
        stage="natural_phrasing",
        metric="fluency_score",
        condition=lambda v: v < 0.5,
        severity=Severity.WARN,
        message="Fluency score below 0.5 — significant phrasing improvements needed",
        baseline=0.85,
    ),
    Rule(
        rule_id="HIGH_CORRECTION_COUNT",
        dtc_code="GRM-001",
        stage="grammar_correction",
        metric="correction_count",
        condition=lambda v: v >= 3,
        severity=Severity.WARN,
        message="3+ grammar corrections required — significant grammatical errors present",
        baseline=0.0,
    ),
]
