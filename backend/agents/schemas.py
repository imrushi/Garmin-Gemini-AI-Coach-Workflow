"""Pydantic v2 schemas for the AI fitness-coach agent system."""

from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, ValidationError, field_validator, model_validator


# ── Enums ────────────────────────────────────────────────────────────────

class TrainingGate(str, Enum):
    PROCEED = "PROCEED"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    REST_RECOMMENDED = "REST_RECOMMENDED"
    MANDATORY_REST = "MANDATORY_REST"


class ReadinessLabel(str, Enum):
    EXCELLENT = "EXCELLENT"      # 85-100
    GOOD = "GOOD"                # 70-84
    MODERATE = "MODERATE"        # 50-69
    POOR = "POOR"                # 30-49
    VERY_POOR = "VERY_POOR"      # 0-29


# ── Signal sub-models ───────────────────────────────────────────────────

class HRVSignal(BaseModel):
    current_ms: float | None = None
    baseline_ms: float | None = None
    deviation_pct: float | None = None
    trend_3d: str | None = None  # "stable", "declining", "improving"


class SleepSignal(BaseModel):
    score: int | None = None          # 0-100
    duration_min: int | None = None
    deep_min: int | None = None
    rem_min: int | None = None
    quality_label: str | None = None  # "poor", "fair", "good", "excellent"


class LoadSignal(BaseModel):
    acwr: float | None = None
    acute_load: float | None = None
    chronic_load: float | None = None
    acwr_risk: str | None = None  # "safe"(<1.0), "optimal"(1.0-1.3), "high"(1.3-1.5), "danger"(>1.5)


class KeySignals(BaseModel):
    hrv: HRVSignal = HRVSignal()
    sleep: SleepSignal = SleepSignal()
    load: LoadSignal = LoadSignal()
    body_battery_morning: int | None = None
    resting_hr: int | None = None
    resting_hr_trend: str | None = None  # "stable", "elevated", "low"
    stress_avg: int | None = None


# ── ReadinessReport ──────────────────────────────────────────────────────

class ReadinessReport(BaseModel):
    report_date: str  # YYYY-MM-DD
    readiness_score: int  # 0-100
    readiness_label: ReadinessLabel
    training_gate: TrainingGate
    key_signals: KeySignals
    flags: list[str] = []
    narrative: str  # 2-3 sentence plain English summary
    recommendations: list[str] = []
    data_completeness_pct: int = 100  # 0-100

    @field_validator("readiness_score")
    @classmethod
    def score_in_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError(f"readiness_score must be 0-100, got {v}")
        return v

    @model_validator(mode="after")
    def low_score_must_rest(self) -> ReadinessReport:
        if self.readiness_score < 30 and self.training_gate not in (
            TrainingGate.MANDATORY_REST,
            TrainingGate.REST_RECOMMENDED,
        ):
            raise ValueError(
                f"readiness_score {self.readiness_score} < 30 requires "
                f"MANDATORY_REST or REST_RECOMMENDED, got {self.training_gate.value}"
            )
        return self

    @classmethod
    def from_llm_response(cls, json_str: str) -> ReadinessReport:
        """Parse an LLM response (possibly wrapped in markdown fences) into a ReadinessReport."""
        cleaned = re.sub(r"```(?:json)?\s*", "", json_str).strip().rstrip("`")
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from LLM: {exc}") from exc
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            failed = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                for e in exc.errors()
            )
            raise ValueError(f"LLM response failed validation — {failed}") from exc


# ── WorkoutSummary ───────────────────────────────────────────────────────

class WorkoutSummary(BaseModel):
    date: str
    sport: str
    duration_min: int | None = None
    distance_m: float | None = None
    avg_hr: int | None = None
    perceived_effort: int | None = None
    feedback_text: str | None = None
