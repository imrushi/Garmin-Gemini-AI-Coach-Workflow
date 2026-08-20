import asyncio
import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from agents.orchestrator import orchestrator
from config import settings
from db.model import AppSettings, DailyMetric, User, UserProfile, get_session
from db.writer import save_daily_metrics, save_workouts
from ingestion.garmin_client import GarminClient
from ingestion.normaliser import normalise_day
from ingestion.zone_utils import fetch_zones_for_activities

logger = logging.getLogger(__name__)

_DEFAULT_PIPELINE_HOUR = 6
_DEFAULT_PIPELINE_MINUTE = 45
_DEFAULT_TIMEZONE = "Asia/Kolkata"


def _offset_time(hour: int, minute: int, delta_minutes: int) -> tuple[int, int]:
    dt = datetime(2000, 1, 1, hour, minute) - timedelta(minutes=delta_minutes)
    return dt.hour, dt.minute


def _load_schedule() -> tuple[int, int, str]:
    with get_session() as session:
        row = session.get(AppSettings, 1)
        if row is None:
            row = AppSettings(
                id=1,
                pipeline_hour=_DEFAULT_PIPELINE_HOUR,
                pipeline_minute=_DEFAULT_PIPELINE_MINUTE,
                timezone=_DEFAULT_TIMEZONE,
            )
            session.add(row)
        return row.pipeline_hour, row.pipeline_minute, row.timezone


class NightlyScheduler:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=_DEFAULT_TIMEZONE)
        self.is_running = False

    def _schedule_jobs(self, hour: int, minute: int, tz: str) -> None:
        pre_sync_h, pre_sync_m = _offset_time(hour, minute, 30)
        morning_sync_h, morning_sync_m = _offset_time(hour, minute, 15)

        self.scheduler.add_job(
            self.run_garmin_sync_range,
            trigger="cron",
            hour=pre_sync_h,
            minute=pre_sync_m,
            id="garmin_sync",
            replace_existing=True,
            misfire_grace_time=3600,
            timezone=tz,
        )
        self.scheduler.add_job(
            self.run_garmin_sync_today,
            trigger="cron",
            hour=morning_sync_h,
            minute=morning_sync_m,
            id="garmin_sync_today",
            replace_existing=True,
            misfire_grace_time=3600,
            timezone=tz,
        )
        self.scheduler.add_job(
            self.run_daily_pipeline,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="daily_pipeline",
            replace_existing=True,
            misfire_grace_time=3600,
            timezone=tz,
        )
        logger.info(
            "Scheduler jobs set: pre-sync %02d:%02d, morning sync %02d:%02d, pipeline %02d:%02d (%s)",
            pre_sync_h, pre_sync_m, morning_sync_h, morning_sync_m, hour, minute, tz,
        )

    def start(self) -> None:
        hour, minute, tz = _load_schedule()
        self.scheduler = AsyncIOScheduler(timezone=tz)
        self._schedule_jobs(hour, minute, tz)
        self.scheduler.start()
        self.is_running = True

    def reschedule(self, hour: int, minute: int, tz: str) -> None:
        self._schedule_jobs(hour, minute, tz)
        logger.info("Scheduler rescheduled to pipeline %02d:%02d (%s)", hour, minute, tz)

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        self.is_running = False

    async def run_garmin_sync_range(self) -> None:
        """Pull last 3 days including today from Garmin for all users."""
        logger.info("Starting Garmin sync (last 3 days)")

        with get_session() as session:
            users = session.execute(select(User)).scalars().all()
            user_ids = [u.id for u in users]

        for user_id in user_ids:
            try:
                with get_session() as session:
                    profile = session.get(UserProfile, user_id)
                    if profile is None:
                        logger.warning("No profile for user %s — skipping", user_id)
                        continue
                    garmin_email = profile.garmin_email
                    garmin_password = profile.garmin_password

                if not garmin_email:
                    logger.warning("No garmin_email for user %s — skipping", user_id)
                    continue

                client = GarminClient(garmin_email, garmin_password or "")
                client.connect()

                for i in range(0, 3):
                    sync_date = date.today() - timedelta(days=i)
                    await self._sync_one_day(client, user_id, sync_date)
                    await asyncio.sleep(2)

                logger.info("Garmin sync complete for user %s", user_id)

            except Exception as e:
                logger.error("Garmin sync failed for user %s: %s", user_id, e)
                continue

    async def run_garmin_sync_today(self) -> None:
        """Morning catch-up sync — today only, captures sleep data for late risers."""
        logger.info("Morning sync: pulling today's sleep and recovery data")

        with get_session() as session:
            users = session.execute(select(User)).scalars().all()
            user_ids = [u.id for u in users]

        for user_id in user_ids:
            try:
                with get_session() as session:
                    profile = session.get(UserProfile, user_id)
                    if profile is None:
                        logger.warning("No profile for user %s — skipping", user_id)
                        continue
                    garmin_email = profile.garmin_email
                    garmin_password = profile.garmin_password

                if not garmin_email:
                    logger.warning("No garmin_email for user %s — skipping", user_id)
                    continue

                client = GarminClient(garmin_email, garmin_password or "")
                client.connect()

                await self._sync_one_day(client, user_id, date.today())

                logger.info("Morning sync complete for user %s", user_id)

            except Exception as e:
                logger.error("Morning sync failed for user %s: %s", user_id, e)
                continue

    async def run_daily_pipeline(self) -> None:
        logger.info("Starting daily analysis + planning pipeline")

        with get_session() as session:
            users = session.execute(select(User)).scalars().all()
            user_ids = [u.id for u in users]

        for user_id in user_ids:
            try:
                result = await orchestrator.run_full_pipeline(user_id, patch_target="today")
                if result.success:
                    score = result.analysis_result.report.readiness_score
                    logger.info("Pipeline complete for %s: score=%s", user_id, score)
                else:
                    logger.error("Pipeline failed for %s: %s", user_id, result.error)
            except Exception as e:
                logger.error("Pipeline exception for %s: %s", user_id, e)

    async def _sync_one_day(
        self,
        client: GarminClient,
        user_id: str,
        sync_date: date,
    ) -> None:
        """Fetch, normalise, fetch zone data, and save one day."""
        date_str = sync_date.strftime("%Y-%m-%d")
        raw = client.fetch_day(date_str)
        metrics = normalise_day(raw, user_id)
        save_daily_metrics(metrics)
        zone_data_map = fetch_zones_for_activities(client, metrics.workouts_json)
        save_workouts(user_id, sync_date, metrics.workouts_json, zone_data_map=zone_data_map)

    def get_todays_sleep_available(self, user_id: str) -> bool:
        """Return True if today's sleep_score has been synced for this user."""
        with get_session() as session:
            row = session.execute(
                select(DailyMetric.sleep_score).where(
                    DailyMetric.user_id == user_id,
                    DailyMetric.date == date.today(),
                )
            ).scalar_one_or_none()
        return row is not None

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_paused": self.scheduler.state == 2,  # STATE_PAUSED = 2
            "jobs": [
                {
                    "id": job.id,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
                for job in self.scheduler.get_jobs()
            ],
        }

    async def sync_single_user(self, user_id: str) -> None:
        logger.info("Manual Garmin sync triggered for user %s", user_id)
        try:
            with get_session() as session:
                profile = session.get(UserProfile, user_id)
                if profile is None:
                    logger.warning("No profile for user %s — skipping", user_id)
                    return
                garmin_email = profile.garmin_email
                garmin_password = profile.garmin_password

            if not garmin_email:
                logger.warning("No garmin_email for user %s — skipping", user_id)
                return

            client = GarminClient(garmin_email, garmin_password or "")
            client.connect()

            for i in range(0, 4):
                sync_date = date.today() - timedelta(days=i)
                await self._sync_one_day(client, user_id, sync_date)
                await asyncio.sleep(2)

            logger.info("Garmin sync complete for user %s", user_id)
        except Exception as e:
            logger.error("Garmin sync failed for user %s: %s", user_id, e)

    async def pipeline_single_user(self, user_id: str) -> None:
        logger.info("Manual pipeline triggered for user %s", user_id)
        try:
            result = await orchestrator.run_full_pipeline(user_id, patch_target="today")
            if result.success:
                score = result.analysis_result.report.readiness_score
                logger.info("Pipeline complete for %s: score=%s", user_id, score)
            else:
                logger.error("Pipeline failed for %s: %s", user_id, result.error)
        except Exception as e:
            logger.error("Pipeline exception for %s: %s", user_id, e)


nightly_scheduler = NightlyScheduler()

