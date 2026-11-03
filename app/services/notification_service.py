from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    BREAK_TIME_END,
    BREAK_TIME_START,
    MEAL_NUDGE_CATALOG,
    PROTEIN_GOAL_G_PER_KG,
    WATER_RETRY_AFTER_NO_MINUTES,
    NotificationStatus,
    NotificationType,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import ensure_utc
from app.models.meal import Meal, MealItem
from app.models.notification import Notification
from app.models.user import User
from app.models.water import WaterLog
from app.schemas.water import WaterLogRequest
from app.services import water_service
from app.services.timezone_utils import local_day_bounds_utc, user_timezone
from app.services.water_goals import should_remind

WATER_CHECK_MESSAGE = "Have you taken 250 ml of water now?"


def _active_users(db: Session) -> list[User]:
    return list(db.execute(select(User).where(User.is_active.is_(True))).scalars())


def _latest_notification(db: Session, user_id: int, ntype: NotificationType) -> Notification | None:
    return db.execute(
        select(Notification)
        .where(Notification.user_id == user_id, Notification.type == ntype)
        .order_by(Notification.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _create_notification(
    db: Session, user: User, ntype: NotificationType, message: str
) -> Notification:
    notification = Notification(
        user_id=user.id,
        type=ntype,
        message=message,
        status=NotificationStatus.PENDING,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(notification)
    return notification


def run_meal_agent_tick(db: Session, now: datetime | None = None) -> None:
    """Checked every scheduler tick. Fires at most once per user per day, only
    inside the office break window, only if today's protein intake is short of a
    rough per-kg target."""
    now = now or datetime.now(UTC)

    for user in _active_users(db):
        now_local = now.astimezone(user_timezone(user))
        if not (BREAK_TIME_START <= now_local.time() < BREAK_TIME_END):
            continue

        day_start, day_end = local_day_bounds_utc(user, now)
        already_sent_today = db.execute(
            select(Notification.id).where(
                Notification.user_id == user.id,
                Notification.type == NotificationType.MEAL_NUDGE,
                Notification.created_at >= day_start,
                Notification.created_at <= day_end,
            )
        ).scalar_one_or_none()
        if already_sent_today is not None:
            continue

        protein_so_far = db.execute(
            select(MealItem.protein_g)
            .join(Meal, Meal.id == MealItem.meal_id)
            .where(
                Meal.user_id == user.id,
                Meal.deleted_at.is_(None),
                Meal.captured_at >= day_start,
                Meal.captured_at <= day_end,
            )
        ).scalars()
        protein_so_far_total = sum(p for p in protein_so_far if p is not None)

        protein_goal = user.weight_kg * PROTEIN_GOAL_G_PER_KG
        remaining = protein_goal - protein_so_far_total
        if remaining <= 0:
            continue

        suggestion = next(
            (item for item in MEAL_NUDGE_CATALOG if item["protein_g"] <= remaining),
            MEAL_NUDGE_CATALOG[0],
        )
        message = (
            f"You have about {remaining:.0f}g protein left for today — how about "
            f"{suggestion['name']}? (~{suggestion['protein_g']}g protein, "
            f"~{suggestion['approx_calories']} kcal) to keep your energy up."
        )
        _create_notification(db, user, NotificationType.MEAL_NUDGE, message)

    db.commit()


def run_water_agent_tick(db: Session, now: datetime | None = None) -> None:
    """Checked every scheduler tick. Mirrors the on-demand water-reminder threshold
    for the first ask, then retries every WATER_RETRY_AFTER_NO_MINUTES after a "no"
    until the user says yes or logs water directly."""
    now = now or datetime.now(UTC)

    for user in _active_users(db):
        last_log = db.execute(
            select(WaterLog)
            .where(WaterLog.user_id == user.id)
            .order_by(WaterLog.logged_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        latest = _latest_notification(db, user.id, NotificationType.WATER_CHECK)

        # If the user logged water after this notification was raised, treat it as
        # implicitly answered — don't keep retrying a "no" they've already acted on.
        if (
            latest is not None
            and latest.status != NotificationStatus.YES
            and last_log is not None
            and ensure_utc(last_log.logged_at) > ensure_utc(latest.created_at)
        ):
            latest.status = NotificationStatus.YES
            latest.responded_at = now
            latest = None

        if latest is not None and latest.status == NotificationStatus.PENDING:
            continue  # already waiting on a response, don't pile up another

        if latest is not None and latest.status == NotificationStatus.NO:
            minutes_since_response = (
                now - ensure_utc(latest.responded_at)
            ).total_seconds() / 60
            due = minutes_since_response >= WATER_RETRY_AFTER_NO_MINUTES
        else:
            due, _reason, _minutes = should_remind(
                last_log_at=ensure_utc(last_log.logged_at) if last_log else None,
                account_created_at=ensure_utc(user.created_at),
                snoozed_until=None,
                now=now,
            )

        if due:
            _create_notification(db, user, NotificationType.WATER_CHECK, WATER_CHECK_MESSAGE)

    db.commit()


def list_pending(db: Session, user: User) -> list[Notification]:
    return list(
        db.execute(
            select(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.status == NotificationStatus.PENDING,
            )
            .order_by(Notification.created_at.desc())
        ).scalars()
    )


def respond_to_notification(
    db: Session, user: User, notification_id: int, response: str
) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("Notification not found", code="notification_not_found")
    if notification.status != NotificationStatus.PENDING:
        raise ValidationError(
            "This notification has already been answered", code="notification_already_answered"
        )

    notification.status = NotificationStatus.YES if response == "yes" else NotificationStatus.NO
    notification.responded_at = datetime.now(UTC)
    notification.updated_by = user.id

    if notification.type == NotificationType.WATER_CHECK and response == "yes":
        water_service.log_water(db, user, WaterLogRequest(source="quick_yes"))

    db.commit()
    db.refresh(notification)
    return notification
