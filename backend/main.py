import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from config import settings
from db.cost_logger import get_cost_summary
from db.model import Base, Job, UserProfile, get_engine, get_session

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


class ModelConfigRequest(BaseModel):
    model_analysis: str
    model_planning: str

    @field_validator("model_analysis", "model_planning")
    @classmethod
    def valid_prefix(cls, v: str) -> str:
        if not (v.startswith("openrouter/") or v.startswith("ollama/")):
            raise ValueError("Model must start with 'openrouter/' or 'ollama/'")
        return v


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
