import json
from datetime import date

from pydantic import BaseModel


# ── Pydantic schema ──────────────────────────────────────────────────────

class DailyMetrics(BaseModel):
    user_id: str
    date: date
    source: str = "garmin"
    active_calories: int | None = None
    total_steps: int | None = None
    avg_resting_hr: int | None = None
    hrv_last_night_ms: float | None = None
    vo2max: float | None = None
    acute_load: float | None = None
    chronic_load: float | None = None
    acwr: float | None = None
    body_battery_min: int | None = None
    body_battery_max: int | None = None
    sleep_score: int | None = None
    sleep_duration_min: int | None = None
    deep_sleep_min: int | None = None
    rem_sleep_min: int | None = None
    stress_avg: int | None = None
    weight_kg: float | None = None
    workouts_json: str | None = None
    raw_garmin_json: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────

def safe_get(d, *keys, default=None):
    """Traverse nested dicts safely, returning *default* on any miss."""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _secs_to_mins(secs) -> int | None:
    if secs is None:
        return None
    try:
        return int(secs) // 60
    except (TypeError, ValueError):
        return None


# ── Extractors ───────────────────────────────────────────────────────────

def _extract_stats(raw: dict | None) -> dict:
    if not raw:
        return {}
    return {
        "total_steps": raw.get("totalSteps"),
        "active_calories": raw.get("activeKilocalories"),
        "avg_resting_hr": raw.get("restingHeartRate"),
        "stress_avg": raw.get("averageStressLevel"),
        "vo2max": raw.get("vo2Max"),
    }


def _extract_sleep(raw: dict | None) -> dict:
    dto = safe_get(raw, "dailySleepDTO") or {}
    scores = safe_get(dto, "sleepScores") or {}
    return {
        "sleep_score": safe_get(scores, "overall", "value"),
        "sleep_duration_min": _secs_to_mins(dto.get("sleepTimeSeconds")),
        "deep_sleep_min": _secs_to_mins(dto.get("deepSleepSeconds")),
        "rem_sleep_min": _secs_to_mins(dto.get("remSleepSeconds")),
    }


def _extract_hrv(raw) -> dict:
    if not raw or not isinstance(raw, dict):
        return {}
    # Try hrvSummary (singular) → {"hrvSummary": {"lastNightAvg": 69, ...}}
    summary = raw.get("hrvSummary")
    if isinstance(summary, dict):
        for key in ("lastNightAvg", "lastNight5MinHigh", "avgHrvValue"):
            val = summary.get(key)
            if val is not None:
                return {"hrv_last_night_ms": float(val)}
    # Try direct top-level keys
    for key in ("lastNightAvg", "lastNight5MinHigh", "avgHrvValue"):
        val = raw.get(key)
        if val is not None:
            return {"hrv_last_night_ms": float(val)}
    # Try nested hrvSummaries list (plural)
    summaries = raw.get("hrvSummaries") or []
    if isinstance(summaries, list) and summaries:
        entry = summaries[-1]
        if isinstance(entry, dict):
            for key in ("lastNightAvg", "lastNight5MinHigh", "avgHrvValue"):
                val = entry.get(key)
                if val is not None:
                    return {"hrv_last_night_ms": float(val)}
    return {}


def _extract_body_battery(raw) -> dict:
    if not raw or not isinstance(raw, list):
        return {}
    values: list[int] = []
    for entry in raw:
        arr = entry.get("bodyBatteryValuesArray") if isinstance(entry, dict) else None
        if not arr:
            continue
        for pair in arr:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2 and pair[1] is not None:
                values.append(int(pair[1]))
    if not values:
        return {}
    return {
        "body_battery_min": min(values),
        "body_battery_max": max(values),
    }


def _extract_weight(raw) -> dict:
    if not raw:
        return {}

    def _kg(w) -> float:
        return round(w / 1000.0 if w > 1000 else float(w), 2)

    # Shape A: dailyWeightSummaries (date-ranged weigh-ins endpoint)
    summaries = safe_get(raw, "dailyWeightSummaries") or []
    for summary in reversed(summaries):
        w = safe_get(summary, "latestWeight", "value")
        if w is None:
            w = safe_get(summary, "maxWeight")
        if w is None:
            w = safe_get(summary, "weight")
        if w is not None:
            return {"weight_kg": _kg(w)}

    # Shape B: dateWeightList (get_weigh_ins range response)
    for day_block in reversed(safe_get(raw, "dateWeightList") or []):
        for entry in reversed(day_block.get("dateWeightList") or []):
            w = entry.get("value")
            if w is not None:
                return {"weight_kg": _kg(w)}

    # Shape C: previousDateWeight — most recent weigh-in before this day
    pdw = raw.get("previousDateWeight")
    if isinstance(pdw, dict):
        w = pdw.get("weight")
        if w is not None:
            return {"weight_kg": _kg(w)}

    # Fallback: totalAverage
    w = safe_get(raw, "totalAverage", "weight")
    if w is not None:
        return {"weight_kg": _kg(w)}
    return {}


def _extract_training_status(raw) -> dict:
    """Extract vo2max + acute/chronic load + ACWR from get_training_status response."""
    if not raw or not isinstance(raw, dict):
        return {}

    result: dict = {}

    # ── VO2Max ────────────────────────────────────────────────────────
    vo2_generic = safe_get(raw, "mostRecentVO2Max", "generic")
    if isinstance(vo2_generic, dict):
        v = vo2_generic.get("vo2MaxPreciseValue") or vo2_generic.get("vo2MaxValue")
        if v is not None:
            result["vo2max"] = float(v)

    # ── Acute / Chronic Load / ACWR ───────────────────────────────────
    # Path: mostRecentTrainingStatus.latestTrainingStatusData.{deviceId}.acuteTrainingLoadDTO
    latest_map = safe_get(raw, "mostRecentTrainingStatus", "latestTrainingStatusData")
    if isinstance(latest_map, dict) and latest_map:
        # Prefer the primary training device; fall back to first entry
        device_entry = None
        for v in latest_map.values():
            if isinstance(v, dict) and v.get("primaryTrainingDevice"):
                device_entry = v
                break
        if device_entry is None:
            device_entry = next((v for v in latest_map.values() if isinstance(v, dict)), None)

        if device_entry:
            atl = device_entry.get("acuteTrainingLoadDTO")
            if isinstance(atl, dict):
                acute = atl.get("dailyTrainingLoadAcute")
                chronic = atl.get("dailyTrainingLoadChronic")
                acwr = atl.get("dailyAcuteChronicWorkloadRatio")
                if acute is not None:
                    result["acute_load"] = round(float(acute), 1)
                if chronic is not None:
                    result["chronic_load"] = round(float(chronic), 1)
                if acwr is not None:
                    result["acwr"] = round(float(acwr), 3)

    return result


def _extract_max_metrics(raw) -> dict:
    """Extract VO2max from get_max_metrics response (fallback/override for training_status)."""
    if not raw:
        return {}
    # API returns a list on days with data; normalise to dict
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        return {}
    # Shape A: allMetrics.metricsMap.VO2MAX_RUNNING[*].value
    met_map = safe_get(raw, "allMetrics", "metricsMap") or {}
    for key in ("VO2MAX_RUNNING", "VO2_MAX_RUNNING", "GENERIC_VO2_MAX"):
        entries = met_map.get(key) or []
        if isinstance(entries, list) and entries:
            val = (entries[-1] or {}).get("value") if isinstance(entries[-1], dict) else None
            if val is not None:
                return {"vo2max": float(val)}
    # Shape B: direct top-level keys
    for key in ("vo2MaxValue", "genericVO2MaxValue", "vo2MaxPreciseValue"):
        v = raw.get(key)
        if v is not None:
            return {"vo2max": float(v)}
    return {}


def _extract_activities(raw) -> dict:
    if not raw or not isinstance(raw, list) or len(raw) == 0:
        return {}
    return {"workouts_json": json.dumps(raw, default=str)}


# ── Main entry point ────────────────────────────────────────────────────

def normalise_day(raw: dict, user_id: str) -> DailyMetrics:
    fields: dict = {}
    fields.update(_extract_stats(raw.get("stats")))
    fields.update(_extract_sleep(raw.get("sleep")))
    fields.update(_extract_hrv(raw.get("hrv")))
    fields.update(_extract_body_battery(raw.get("body_battery")))
    fields.update(_extract_training_status(raw.get("training_status")))
    # max_metrics gives a more precise vo2max — overrides the stats value if present
    fields.update(_extract_max_metrics(raw.get("max_metrics")))
    fields.update(_extract_weight(raw.get("weight")))
    fields.update(_extract_activities(raw.get("activities")))

    return DailyMetrics(
        user_id=user_id,
        date=raw["date"],
        raw_garmin_json=json.dumps(raw, default=str),
        **fields,
    )
