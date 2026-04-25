"""Read helpers that load DB data for agent consumption."""

from __future__ import annotations

import json
import logging
import math
from datetime import date, timedelta

from sqlalchemy import func, select

from db.model import (
    DailyMetric,
    UserFeedback,
    UserProfile,
    Workout,
    get_session,
)

log = logging.getLogger(__name__)

# Columns to exclude from DailyMetric dicts (too large / internal)
_METRIC_EXCLUDE = {"raw_garmin_json", "_sa_instance_state"}


def get_recent_metrics(user_id: str, days: int = 14) -> list[dict]:
    """Return the last *days* daily-metric rows for *user_id*, oldest-first."""
    cutoff = date.today() - timedelta(days=days)
    with get_session() as s:
        rows = (
            s.execute(
                select(DailyMetric)
                .where(DailyMetric.user_id == user_id, DailyMetric.date >= cutoff)
                .order_by(DailyMetric.date.desc())
                .limit(days)
            )
            .scalars()
            .all()
        )
        results: list[dict] = []
        for r in reversed(rows):  # oldest-first
            d = {k: v for k, v in r.__dict__.items() if k not in _METRIC_EXCLUDE}
            # Parse workouts_json string → list
            wj = d.get("workouts_json")
            if isinstance(wj, str):
                try:
                    d["workouts_json"] = json.loads(wj)
                except json.JSONDecodeError:
                    d["workouts_json"] = []
            results.append(d)
    return results


def get_hrv_baseline(user_id: str, days: int = 28) -> float | None:
    """Average HRV over the last *days* days.  Returns None if < 3 data points."""
    cutoff = date.today() - timedelta(days=days)
    with get_session() as s:
        rows = (
            s.execute(
                select(DailyMetric.hrv_last_night_ms)
                .where(
                    DailyMetric.user_id == user_id,
                    DailyMetric.date >= cutoff,
                    DailyMetric.hrv_last_night_ms.is_not(None),
                )
            )
            .scalars()
            .all()
        )
    if len(rows) < 3:
        return None
    return sum(rows) / len(rows)


def get_recent_workouts(user_id: str, days: int = 7) -> list[dict]:
    """Return recent workouts (no raw_json), newest-first."""
    cutoff = date.today() - timedelta(days=days)
    with get_session() as s:
        rows = (
            s.execute(
                select(Workout)
                .where(Workout.user_id == user_id, Workout.date >= cutoff)
                .order_by(Workout.date.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "date": str(r.date),
                "sport": r.sport,
                "duration_min": r.duration_min,
                "distance_m": r.distance_m,
                "avg_hr": r.avg_hr,
                "perceived_effort": r.perceived_effort,
            }
            for r in rows
        ]


def get_recent_feedback(user_id: str, days: int = 7) -> list[dict]:
    """Return recent user feedback rows."""
    cutoff = date.today() - timedelta(days=days)
    with get_session() as s:
        rows = (
            s.execute(
                select(UserFeedback)
                .where(UserFeedback.user_id == user_id, UserFeedback.feedback_date >= cutoff)
                .order_by(UserFeedback.feedback_date.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "feedback_date": str(r.feedback_date),
                "free_text": r.free_text,
                "perceived_effort": r.perceived_effort,
                "mood": r.mood,
                "override_choice": r.override_choice,
            }
            for r in rows
        ]


def get_user_profile(user_id: str) -> dict | None:
    """Load the user profile as a plain dict, parsing JSON list fields."""
    with get_session() as s:
        profile = s.get(UserProfile, user_id)
        if profile is None:
            return None
        d = {k: v for k, v in profile.__dict__.items() if k != "_sa_instance_state"}
        for field in ("medical_conditions", "dietary_allergies"):
            raw = d.get(field)
            if isinstance(raw, str):
                try:
                    d[field] = json.loads(raw)
                except json.JSONDecodeError:
                    d[field] = [raw] if raw else []
        return d


def compute_acwr(user_id: str) -> tuple[float | None, float | None, float | None]:
    """Return (acute_load, chronic_load, acwr) using active_calories as proxy."""
    today = date.today()
    cutoff_28 = today - timedelta(days=28)
    with get_session() as s:
        rows = (
            s.execute(
                select(DailyMetric.date, DailyMetric.active_calories)
                .where(
                    DailyMetric.user_id == user_id,
                    DailyMetric.date >= cutoff_28,
                    DailyMetric.active_calories.is_not(None),
                )
                .order_by(DailyMetric.date.desc())
            )
            .all()
        )
    if not rows:
        return (None, None, None)

    cutoff_7 = today - timedelta(days=7)
    acute_vals = [cal for d, cal in rows if d >= cutoff_7]
    chronic_vals = [cal for _, cal in rows]

    acute = sum(acute_vals) / len(acute_vals) if acute_vals else None
    chronic = sum(chronic_vals) / len(chronic_vals) if chronic_vals else None

    if acute is None or chronic is None or chronic == 0:
        return (acute, chronic, None)

    acwr = round(acute / chronic, 2)
    return (acute, chronic, acwr)


def get_weeks_to_goal(user_id: str) -> int | None:
    """Weeks remaining until the user's goal_date, or None if unset."""
    with get_session() as s:
        profile = s.get(UserProfile, user_id)
        if profile is None or profile.goal_date is None:
            return None
        delta = profile.goal_date - date.today()
        if delta.days <= 0:
            return 0
        return math.ceil(delta.days / 7)
