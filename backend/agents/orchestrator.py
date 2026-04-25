"""Orchestrator — manages the daily pipeline execution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from agents.analysis_agent import AnalysisAgent, AnalysisResult
from agents.planning_agent import PlanningAgent, PlanningResult
from agents.schemas import ReadinessReport
from db.model import Job, get_session
from db.reader import get_user_profile

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    user_id: str
    run_date: str
    analysis_result: AnalysisResult | None = None
    planning_result: PlanningResult | None = None
    error: str | None = None
    success: bool = False


class AgentOrchestrator:
    async def run_analysis(
        self, user_id: str, target_date: str | None = None
    ) -> PipelineResult:
        run_date = target_date or str(date.today())
        result = PipelineResult(user_id=user_id, run_date=run_date)
        job_id = str(uuid4())

        # Step 1 — Create job record
        with get_session() as s:
            s.add(Job(id=job_id, user_id=user_id, job_type="analysis", status="running"))

        # Step 2 — Resolve model from profile
        profile = get_user_profile(user_id)
        if profile is None:
            err = f"No profile found for user {user_id}"
            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = err
            result.error = err
            logger.error(err)
            return result

        model_str = profile.get(
            "model_analysis", "openrouter/anthropic/claude-sonnet-4.6"
        )

        # Step 3 — Run Analysis Agent
        try:
            agent = AnalysisAgent(user_id=user_id, model_str=model_str)
            analysis = await agent.run(target_date)
            result.analysis_result = analysis
            result.success = True

            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "done"
                    job.payload = json.dumps(
                        {
                            "score": analysis.report.readiness_score,
                            "gate": analysis.report.training_gate.value,
                        }
                    )

            logger.info(
                "Pipeline complete for %s: score=%d",
                user_id,
                analysis.report.readiness_score,
            )
        except Exception as e:
            result.error = str(e)
            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
            logger.exception("Pipeline failed for %s", user_id)

        return result

    async def run_planning(
        self,
        user_id: str,
        readiness_report: ReadinessReport,
        override_choice: str | None = None,
    ) -> PipelineResult:
        run_date = str(date.today())
        result = PipelineResult(user_id=user_id, run_date=run_date)
        job_id = str(uuid4())

        with get_session() as s:
            s.add(Job(id=job_id, user_id=user_id, job_type="planning", status="running"))

        profile = get_user_profile(user_id)
        if profile is None:
            err = f"No profile found for user {user_id}"
            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = err
            result.error = err
            logger.error(err)
            return result

        model_str = profile.get(
            "model_planning", "openrouter/anthropic/claude-sonnet-4.6"
        )

        try:
            agent = PlanningAgent(user_id=user_id, model_str=model_str)
            planning = await agent.run(readiness_report, override_choice)
            result.planning_result = planning
            result.success = True

            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "done"
                    job.payload = json.dumps({"plan_id": planning.plan_db_id})

            logger.info(
                "Planning complete for %s: plan_id=%s",
                user_id,
                planning.plan_db_id,
            )
        except Exception as e:
            result.error = str(e)
            with get_session() as s:
                job = s.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error = str(e)
            logger.exception("Planning failed for %s", user_id)

        return result

    async def run_full_pipeline(
        self, user_id: str, override_choice: str | None = None
    ) -> PipelineResult:
        result = await self.run_analysis(user_id)
        if not result.success:
            return result

        planning = await self.run_planning(
            user_id, result.analysis_result.report, override_choice
        )
        result.planning_result = planning.planning_result

        logger.info("Full pipeline complete for %s", user_id)
        return result


orchestrator = AgentOrchestrator()
