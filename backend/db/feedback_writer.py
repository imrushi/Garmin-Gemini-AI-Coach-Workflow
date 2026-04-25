"""Feedback writer — saves user check-ins and overrides."""

from __future__ import annotations

import logging
from datetime import date
from uuid import uuid4

from sqlalchemy import select

from db.model import UserFeedback, get_session

logger = logging.getLogger(__name__)


def save_check_in(
    user_id: str,
    check_in_date: str,
    perceived_effort: int | None,
    mood: int | None,
    free_text: str | None,
    override_choice: str | None = None,
    override_reason: str | None = None,
) -> str:
    """Save or update a daily check-in for the given user and date."""
    fb_date = date.fromisoformat(check_in_date)

    with get_session() as session:
        existing = session.execute(
            select(UserFeedback).where(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback_date == fb_date,
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.perceived_effort = perceived_effort
            existing.mood = mood
            existing.free_text = free_text
            existing.override_choice = override_choice
            existing.override_reason = override_reason
            logger.info("Updated check-in %s for %s on %s", existing.id, user_id, check_in_date)
            return existing.id

        fb_id = str(uuid4())
        session.add(
            UserFeedback(
                id=fb_id,
                user_id=user_id,
                feedback_date=fb_date,
                perceived_effort=perceived_effort,
                mood=mood,
                free_text=free_text,
                override_choice=override_choice,
                override_reason=override_reason,
            )
        )
        logger.info("Saved check-in %s for %s on %s", fb_id, user_id, check_in_date)
        return fb_id


def get_todays_override(user_id: str) -> str | None:
    """Return today's override_choice for the user, or None."""
    with get_session() as session:
        row = session.execute(
            select(UserFeedback.override_choice).where(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback_date == date.today(),
            )
        ).scalar_one_or_none()
    return row


def has_active_override(user_id: str, for_date: str) -> tuple[bool, str | None]:
    """Check if the user has an active override for the given date."""
    with get_session() as session:
        choice = session.execute(
            select(UserFeedback.override_choice).where(
                UserFeedback.user_id == user_id,
                UserFeedback.feedback_date == date.fromisoformat(for_date),
            )
        ).scalar_one_or_none()

    if choice in ("push_through", "rest_as_recommended"):
        return True, choice
    return False, None
