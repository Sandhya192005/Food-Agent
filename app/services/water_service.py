from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_QUICK_WATER_AMOUNT_ML
from app.db.base import ensure_utc
from app.models.user import User
from app.models.water import WaterLog, WaterReminderSnooze
from app.schemas.water import WaterLogRequest, WaterReminderOut, WaterTodayOut
from app.services.water_goals import next_snooze_until, reminder_message, should_remind


def _user_timezone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _local_day_bounds_utc(user: User, now: datetime | None = None) -> tuple[datetime, datetime]:
    tz = _user_timezone(user)
    now_local = (now or datetime.now(UTC)).astimezone(tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    end_local = datetime.combine(now_local.date(), time.max, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def log_water(db: Session, user: User, payload: WaterLogRequest) -> WaterLog:
    amount_ml = payload.resolved_amount_ml(DEFAULT_QUICK_WATER_AMOUNT_ML)
    water_log = WaterLog(
        user_id=user.id,
        amount_ml=amount_ml,
        source=payload.source,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(water_log)

    snooze = db.execute(
        select(WaterReminderSnooze).where(WaterReminderSnooze.user_id == user.id)
    ).scalar_one_or_none()
    if snooze is not None:
        db.delete(snooze)

    db.commit()
    db.refresh(water_log)
    return water_log


def get_today_summary(db: Session, user: User) -> WaterTodayOut:
    start_utc, end_utc = _local_day_bounds_utc(user)
    consumed_ml = (
        db.execute(
            select(func.coalesce(func.sum(WaterLog.amount_ml), 0)).where(
                WaterLog.user_id == user.id,
                WaterLog.logged_at >= start_utc,
                WaterLog.logged_at <= end_utc,
            )
        ).scalar_one()
        or 0
    )
    goal_ml = user.daily_water_goal_ml or 2000
    percent = round(min(consumed_ml / goal_ml, 1.0) * 100, 1) if goal_ml else 0.0
    remaining_ml = max(goal_ml - consumed_ml, 0)

    return WaterTodayOut(
        consumed_ml=consumed_ml,
        goal_ml=goal_ml,
        percent=percent,
        remaining_ml=remaining_ml,
    )


def get_reminder_status(db: Session, user: User) -> WaterReminderOut:
    last_log = db.execute(
        select(WaterLog)
        .where(WaterLog.user_id == user.id)
        .order_by(WaterLog.logged_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    snooze = db.execute(
        select(WaterReminderSnooze).where(WaterReminderSnooze.user_id == user.id)
    ).scalar_one_or_none()

    remind, reason, minutes_since = should_remind(
        last_log_at=ensure_utc(last_log.logged_at) if last_log else None,
        account_created_at=ensure_utc(user.created_at),
        snoozed_until=ensure_utc(snooze.snoozed_until) if snooze else None,
    )

    return WaterReminderOut(
        should_remind=remind,
        reason=reason,
        message=reminder_message() if remind else None,
        minutes_since_last=minutes_since,
        quick_actions=["yes_250ml", "choose_amount", "remind_later"] if remind else [],
    )


def snooze_reminder(db: Session, user: User) -> None:
    snoozed_until = next_snooze_until()
    snooze = db.execute(
        select(WaterReminderSnooze).where(WaterReminderSnooze.user_id == user.id)
    ).scalar_one_or_none()

    if snooze is None:
        snooze = WaterReminderSnooze(user_id=user.id, snoozed_until=snoozed_until)
        db.add(snooze)
    else:
        snooze.snoozed_until = snoozed_until

    db.commit()
