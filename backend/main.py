import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from agents.orchestrator import orchestrator
from agents.plan_schemas import CheckInRequest
from agents.schemas import ReadinessReport
from config import settings
from db.cost_logger import get_cost_summary
from db.feedback_writer import get_todays_override, save_check_in
from db.model import (
    Base,
    DailyMetric,
    Job,
    ReadinessReportRow,
    TrainingPlanRow,
    UserFeedback,
    UserProfile,
    get_engine,
    get_session,
)

# ── Lifespan ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    Base.metadata.create_all(get_engine())
    yield


# ── App ──────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Fitness Coach API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────

_VALID_DIETS = {"omnivore", "vegetarian", "vegan", "vegan-junk"}


def _profile_to_dict(p: UserProfile) -> dict:
    return {
        "user_id": p.user_id,
        "display_name": p.display_name,
        "goal_event": p.goal_event,
        "goal_date": str(p.goal_date) if p.goal_date else None,
        "fitness_level": p.fitness_level,
        "medical_conditions": p.medical_conditions,
        "dietary_preference": p.dietary_preference,
        "dietary_allergies": p.dietary_allergies,
        "max_weekly_hours": p.max_weekly_hours,
        "garmin_email": p.garmin_email,
        "swim_equipment": p.swim_equipment,
        "swim_strokes": p.swim_strokes,
        "model_analysis": p.model_analysis,
        "model_planning": p.model_planning,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── Request / Response Models ────────────────────────────────────────────


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    goal_event: str | None = None
    goal_date: date | None = None
    fitness_level: str | None = None
    medical_conditions: str | None = None
    dietary_preference: str | None = None
    dietary_allergies: str | None = None
    max_weekly_hours: float | None = None
    garmin_email: str | None = None
    garmin_password: str | None = None
    swim_equipment: str | None = None  # e.g. "pull_buoy,paddles"
    swim_strokes: str | None = None    # e.g. "freestyle:expert,breaststroke:expert,backstroke:beginner,butterfly:learning"

    @field_validator("goal_date")
    @classmethod
    def goal_date_in_future(cls, v: date | None) -> date | None:
        if v is not None and v <= date.today():
            raise ValueError("goal_date must be in the future")
        return v

    @field_validator("dietary_preference")
    @classmethod
    def valid_diet(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_DIETS:
            raise ValueError(f"dietary_preference must be one of {_VALID_DIETS}")
        return v


class RunAnalysisRequest(BaseModel):
    user_id: str
    target_date: str | None = None


class RunAnalysisResponse(BaseModel):
    success: bool
    report_date: str
    readiness_score: int | None = None
    readiness_label: str | None = None
    training_gate: str | None = None
    narrative: str | None = None
    flags: list[str] = []
    tokens_used: int | None = None
    latency_ms: int | None = None
    error: str | None = None


class ModelConfigRequest(BaseModel):
    model_analysis: str
    model_planning: str

    @field_validator("model_analysis", "model_planning")
    @classmethod
    def valid_prefix(cls, v: str) -> str:
        if not (v.startswith("openrouter/") or v.startswith("ollama/")):
            raise ValueError("Model must start with 'openrouter/' or 'ollama/'")
        return v


class RunPipelineRequest(BaseModel):
    user_id: str
    override_choice: str | None = None


class RunPipelineResponse(BaseModel):
    success: bool
    readiness_score: int | None = None
    training_gate: str | None = None
    plan_valid_from: str | None = None
    plan_valid_to: str | None = None
    session_count: int | None = None
    total_tokens_used: int | None = None
    error: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/profile/{user_id}")
def get_profile(user_id: str):
    with get_session() as session:
        profile = session.get(UserProfile, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return _profile_to_dict(profile)


@app.put("/api/profile/{user_id}")
def update_profile(user_id: str, body: UpdateProfileRequest):
    with get_session() as session:
        profile = session.get(UserProfile, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        updates = body.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(profile, field, value)
        profile.updated_at = datetime.now(timezone.utc)
        session.flush()
        return _profile_to_dict(profile)


@app.get("/api/profile/{user_id}/model-config")
def get_model_config(user_id: str):
    with get_session() as session:
        profile = session.get(UserProfile, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {
            "model_analysis": profile.model_analysis,
            "model_planning": profile.model_planning,
        }


@app.put("/api/profile/{user_id}/model-config")
def update_model_config(user_id: str, body: ModelConfigRequest):
    with get_session() as session:
        profile = session.get(UserProfile, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        changed = (
            profile.model_analysis != body.model_analysis
            or profile.model_planning != body.model_planning
        )
        profile.model_analysis = body.model_analysis
        profile.model_planning = body.model_planning
        profile.updated_at = datetime.now(timezone.utc)
        return {"updated": True, "context_transfer_required": changed}


@app.get("/api/costs/{user_id}")
def get_costs(user_id: str):
    return get_cost_summary(user_id, days=7)


# ── Analysis Endpoints ───────────────────────────────────────────────────


@app.post("/api/analysis/run")
async def run_analysis(body: RunAnalysisRequest):
    result = await orchestrator.run_analysis(body.user_id, body.target_date)
    if not result.success or result.analysis_result is None:
        return RunAnalysisResponse(
            success=False,
            report_date=result.run_date,
            error=result.error or "Unknown error",
        )
    ar = result.analysis_result
    return RunAnalysisResponse(
        success=True,
        report_date=result.run_date,
        readiness_score=ar.report.readiness_score,
        readiness_label=ar.report.readiness_label.value,
        training_gate=ar.report.training_gate.value,
        narrative=ar.report.narrative,
        flags=ar.report.flags,
        tokens_used=ar.prompt_tokens + ar.completion_tokens,
        latency_ms=ar.latency_ms,
    )


@app.get("/api/analysis/report/{user_id}")
async def get_analysis_report(
    user_id: str,
    report_date: str = Query(default=None),
):
    rd = report_date or str(date.today())
    with get_session() as session:
        row = session.execute(
            select(ReadinessReportRow).where(
                ReadinessReportRow.user_id == user_id,
                ReadinessReportRow.report_date == date.fromisoformat(rd),
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="No report found for this date")
        return {
            **json.loads(row.report_json),
            "model_used": row.model_used,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
        }


@app.get("/api/analysis/history/{user_id}")
async def get_analysis_history(
    user_id: str,
    days: int = Query(default=14, ge=1, le=365),
):
    cutoff = date.today() - timedelta(days=days)
    with get_session() as session:
        rows = (
            session.execute(
                select(ReadinessReportRow)
                .where(
                    ReadinessReportRow.user_id == user_id,
                    ReadinessReportRow.report_date >= cutoff,
                )
                .order_by(ReadinessReportRow.report_date.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "report_date": str(r.report_date),
                "readiness_score": r.readiness_score,
                "readiness_label": r.readiness_label,
                "training_gate": r.training_gate,
                "flags": json.loads(r.report_json).get("flags", []),
            }
            for r in rows
        ]


# ── Pipeline Endpoint ─────────────────────────────────────────────────────


@app.post("/api/pipeline/run")
async def run_pipeline(body: RunPipelineRequest):
    result = await orchestrator.run_full_pipeline(body.user_id, body.override_choice)
    if not result.success or result.analysis_result is None:
        return RunPipelineResponse(
            success=False,
            error=result.error or "Unknown error",
        )
    ar = result.analysis_result
    pr = result.planning_result
    total_tokens = ar.prompt_tokens + ar.completion_tokens
    resp = RunPipelineResponse(
        success=True,
        readiness_score=ar.report.readiness_score,
        training_gate=ar.report.training_gate.value,
    )
    if pr is not None:
        total_tokens += pr.prompt_tokens + pr.completion_tokens
        resp.plan_valid_from = pr.plan.valid_from
        resp.plan_valid_to = pr.plan.valid_to
        resp.session_count = len(pr.plan.sessions)
    resp.total_tokens_used = total_tokens
    return resp


# ── Plan Endpoints ────────────────────────────────────────────────────────


@app.get("/api/plans/current/{user_id}")
def get_current_plan(user_id: str):
    with get_session() as session:
        row = session.execute(
            select(TrainingPlanRow).where(
                TrainingPlanRow.user_id == user_id,
                TrainingPlanRow.is_current == True,  # noqa: E712
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="No current plan found")
        plan = json.loads(row.plan_json)
        return {
            **plan,
            "_meta": {
                "generated_at": row.generated_at.isoformat() if row.generated_at else None,
                "model_used": row.model_used,
                "tokens_in": row.tokens_in,
                "tokens_out": row.tokens_out,
            },
        }


@app.get("/api/plans/{user_id}/session/{session_date}")
def get_plan_session(user_id: str, session_date: str):
    with get_session() as session:
        row = session.execute(
            select(TrainingPlanRow).where(
                TrainingPlanRow.user_id == user_id,
                TrainingPlanRow.is_current == True,  # noqa: E712
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="No current plan found")
        plan = json.loads(row.plan_json)
        for sess in plan.get("sessions", []):
            if sess.get("date") == session_date:
                return sess
        raise HTTPException(status_code=404, detail=f"No session found for {session_date}")


@app.get("/api/plans/history/{user_id}")
def get_plan_history(
    user_id: str,
    limit: int = Query(default=5, ge=1, le=50),
):
    with get_session() as session:
        rows = (
            session.execute(
                select(TrainingPlanRow)
                .where(TrainingPlanRow.user_id == user_id)
                .order_by(TrainingPlanRow.valid_from.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "plan_id": r.id,
                "valid_from": str(r.valid_from),
                "valid_to": str(r.valid_to),
                "training_gate": r.training_gate,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            }
            for r in rows
        ]


# ── Check-in Endpoints ────────────────────────────────────────────────────


@app.post("/api/checkin")
async def submit_checkin(body: CheckInRequest):
    fb_id = save_check_in(
        user_id=body.user_id,
        check_in_date=body.check_in_date,
        perceived_effort=body.perceived_effort,
        mood=body.mood,
        free_text=body.free_text,
        override_choice=body.override_choice,
        override_reason=body.override_reason,
    )

    plan_updated = False
    if body.override_choice is not None:
        with get_session() as session:
            report_row = session.execute(
                select(ReadinessReportRow)
                .where(ReadinessReportRow.user_id == body.user_id)
                .order_by(ReadinessReportRow.report_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            report_json = report_row.report_json if report_row is not None else None

        if report_json is not None:
            report = ReadinessReport.model_validate_json(report_json)
            if report.training_gate.value in ("REST_RECOMMENDED", "MANDATORY_REST"):
                await orchestrator.run_planning(
                    body.user_id,
                    report,
                    override_choice=body.override_choice,
                )
                plan_updated = True

    msg = "Plan updated based on your decision." if plan_updated else "Check-in saved."
    return {
        "saved": True,
        "feedback_id": fb_id,
        "override_applied": body.override_choice,
        "plan_updated": plan_updated,
        "message": msg,
    }


@app.get("/api/checkin/today/{user_id}")
def get_today_checkin(user_id: str):
    with get_session() as session:
        row = session.execute(
            select(UserFeedback).where(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback_date == date.today(),
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "feedback_date": str(row.feedback_date),
            "perceived_effort": row.perceived_effort,
            "mood": row.mood,
            "free_text": row.free_text,
            "override_choice": row.override_choice,
            "override_reason": row.override_reason,
        }


# ── Override Prompt Endpoint ──────────────────────────────────────────────


@app.get("/api/plans/override-prompt/{user_id}")
def get_override_prompt(user_id: str):
    with get_session() as session:
        report_row = session.execute(
            select(ReadinessReportRow)
            .where(ReadinessReportRow.user_id == user_id)
            .order_by(ReadinessReportRow.report_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if report_row is None:
            return {
                "show_prompt": False,
                "training_gate": None,
                "readiness_score": None,
                "narrative": None,
                "already_decided": False,
                "decision": None,
            }

        report = json.loads(report_row.report_json)
        gate = report_row.training_gate
        readiness_score = report_row.readiness_score

    show = gate in ("REST_RECOMMENDED", "MANDATORY_REST")
    decision = get_todays_override(user_id)
    already_decided = decision is not None

    return {
        "show_prompt": show,
        "training_gate": gate,
        "readiness_score": readiness_score,
        "narrative": report.get("narrative"),
        "already_decided": already_decided,
        "decision": decision,
    }


# ── Metrics Endpoint ──────────────────────────────────────────────────────


@app.get("/api/metrics/kpi/{user_id}")
def get_kpi_metrics(
    user_id: str,
    days: int = Query(default=14, ge=1, le=365),
):
    cutoff = date.today() - timedelta(days=days - 1)

    with get_session() as session:
        metric_rows = (
            session.execute(
                select(DailyMetric)
                .where(
                    DailyMetric.user_id == user_id,
                    DailyMetric.date >= cutoff,
                )
                .order_by(DailyMetric.date.asc())
            )
            .scalars()
            .all()
        )
        report_rows = (
            session.execute(
                select(ReadinessReportRow)
                .where(
                    ReadinessReportRow.user_id == user_id,
                    ReadinessReportRow.report_date >= cutoff,
                )
            )
            .scalars()
            .all()
        )

    # Index by date string for O(1) lookup
    metrics_by_date: dict[str, DailyMetric] = {
        str(r.date): r for r in metric_rows
    }
    readiness_by_date: dict[str, int] = {
        str(r.report_date): r.readiness_score for r in report_rows
    }

    # Build parallel arrays over every date in the range
    result: dict[str, list] = {
        "dates": [],
        "readiness_scores": [],
        "hrv_ms": [],
        "sleep_scores": [],
        "body_battery_max": [],
        "acwr": [],
        "resting_hr": [],
        "total_steps": [],
        "active_calories": [],
    }

    for offset in range(days):
        d = cutoff + timedelta(days=offset)
        ds = str(d)
        m = metrics_by_date.get(ds)

        result["dates"].append(ds)
        result["readiness_scores"].append(readiness_by_date.get(ds))
        result["hrv_ms"].append(m.hrv_last_night_ms if m else None)
        result["sleep_scores"].append(m.sleep_score if m else None)
        result["body_battery_max"].append(m.body_battery_max if m else None)
        result["acwr"].append(m.acwr if m else None)
        result["resting_hr"].append(m.avg_resting_hr if m else None)
        result["total_steps"].append(m.total_steps if m else None)
        result["active_calories"].append(m.active_calories if m else None)

    return result


# ── Job Endpoints ─────────────────────────────────────────────────────────


@app.get("/api/jobs/{user_id}")
def get_jobs(user_id: str):
    with get_session() as session:
        rows = session.execute(
            select(Job)
            .where(Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(10)
        ).scalars().all()
        return [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "payload": j.payload,
                "error": j.error,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None,
            }
            for j in rows
        ]
