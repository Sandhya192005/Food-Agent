from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.constants import (
    WATER_ACTIVITY_BONUS_ML,
    WATER_GOAL_MAX_ML,
    WATER_GOAL_MIN_ML,
    WATER_GOAL_ML_PER_KG,
    ActivityLevel,
)


def calculate_daily_water_goal_ml(weight_kg: float, activity_level: ActivityLevel) -> int:
    base_ml = weight_kg * WATER_GOAL_ML_PER_KG
    bonus_ml = WATER_ACTIVITY_BONUS_ML[activity_level]
    goal_ml = round(base_ml + bonus_ml)
    return max(WATER_GOAL_MIN_ML, min(goal_ml, WATER_GOAL_MAX_ML))


def should_remind(
    *,
    last_log_at: datetime | None,
    account_created_at: datetime,
    snoozed_until: datetime | None,
    now: datetime | None = None,
) -> tuple[bool, str, int]:
    """Returns (should_remind, reason, minutes_since_last)."""
    now = now or datetime.now(UTC)

    if snoozed_until is not None and snoozed_until > now:
        reference = last_log_at or account_created_at
        minutes_since = int((now - reference).total_seconds() // 60)
        return False, "snoozed", minutes_since

    reference = last_log_at or account_created_at
    minutes_since = int((now - reference).total_seconds() // 60)

    if minutes_since >= settings.WATER_REMINDER_THRESHOLD_MINUTES:
        return True, "threshold_exceeded", minutes_since

    return False, "recently_logged", minutes_since


def next_snooze_until(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now + timedelta(minutes=settings.WATER_SNOOZE_MINUTES)


def reminder_message() -> str:
    return "💧 Hi! Have you had any water recently? I can update your hydration progress."
