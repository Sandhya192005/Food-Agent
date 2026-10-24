from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.constants import MealType
from app.core.exceptions import NotFoundError, ValidationError
from app.models.skipped_meal import SkippedMeal
from app.models.user import User
from app.services.timezone_utils import user_timezone

# Same reach as logging a missed meal.
MAX_SKIP_BACKDATE = timedelta(days=7)


def _today(user: User) -> date:
    return datetime.now(UTC).astimezone(user_timezone(user)).date()


def skip_meal(
    db: Session, user: User, meal_type: MealType, skip_date: date | None = None
) -> SkippedMeal:
    """Marks a meal as skipped. Skipping the same meal twice returns the same row."""
    skipped = _add_skip(db, user, meal_type, skip_date or _today(user))
    db.commit()
    db.refresh(skipped)
    return skipped


def _add_skip(db: Session, user: User, meal_type: MealType, skip_date: date) -> SkippedMeal:
    """Validates and adds (without committing) a skip, or returns the existing one."""
    today = _today(user)
    if meal_type == MealType.SNACK:
        raise ValidationError("Only breakfast, lunch or dinner can be skipped", code="cannot_skip")
    if skip_date > today:
        raise ValidationError("Can't skip a meal on a future day", code="skip_date_in_future")
    if skip_date < today - MAX_SKIP_BACKDATE:
        raise ValidationError("Can only skip meals up to 7 days back", code="skip_date_too_old")

    existing = db.execute(
        select(SkippedMeal).where(
            SkippedMeal.user_id == user.id,
            SkippedMeal.skip_date == skip_date,
            SkippedMeal.meal_type == meal_type,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    skipped = SkippedMeal(
        user_id=user.id,
        skip_date=skip_date,
        meal_type=meal_type,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(skipped)
    db.flush()
    return skipped


def list_skipped(db: Session, user: User, on_date: date | None = None) -> list[SkippedMeal]:
    day = on_date or _today(user)
    return list(
        db.execute(
            select(SkippedMeal)
            .where(SkippedMeal.user_id == user.id, SkippedMeal.skip_date == day)
            .order_by(SkippedMeal.id)
        ).scalars()
    )


def undo_skip(db: Session, user: User, skip_id: int) -> None:
    result = db.execute(
        delete(SkippedMeal).where(SkippedMeal.id == skip_id, SkippedMeal.user_id == user.id)
    )
    if result.rowcount == 0:
        raise NotFoundError("Skipped meal not found", code="skipped_meal_not_found")
    db.commit()


def clear_skip(db: Session, user: User, skip_date: date, meal_type: MealType) -> None:
    """Called when the user logs a meal they had marked as skipped. Doesn't commit."""
    db.execute(
        delete(SkippedMeal).where(
            SkippedMeal.user_id == user.id,
            SkippedMeal.skip_date == skip_date,
            SkippedMeal.meal_type == meal_type,
        )
    )
