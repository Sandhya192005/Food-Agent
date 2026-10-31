import json
import mimetypes
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import MEAL_STATUS_ANALYZED
from app.core.exceptions import NotFoundError
from app.models.meal import Meal, MealItem
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse, MealItemOut
from app.services import meal_validation
from app.services.ai import vision_service
from app.services.storage import factory
from app.services.storage.base import StorageBackend
from app.services.timezone_utils import user_timezone


def to_response(meal: Meal, warnings: list[str], is_duplicate: bool) -> MealAnalyzeResponse:
    return MealAnalyzeResponse(
        meal_id=meal.id,
        is_duplicate=is_duplicate,
        total_calories=meal.total_calories or 0,
        items=[MealItemOut.from_model(item) for item in meal.items],
        warnings=warnings,
        source=meal.source,
    )


def analyze_and_store_meal(
    db: Session,
    user: User,
    storage: StorageBackend,
    *,
    raw_bytes: bytes,
    filename: str,
    content_type: str | None,
) -> MealAnalyzeResponse:
    meal_validation.validate_content_type(content_type)
    meal_validation.validate_size(len(raw_bytes))
    meal_validation.validate_image_bytes(raw_bytes)

    image_hash = meal_validation.compute_image_hash(raw_bytes)

    duplicate = meal_validation.find_recent_duplicate(db, user.id, image_hash)
    if duplicate is not None:
        duplicate = db.execute(
            select(Meal).options(selectinload(Meal.items)).where(Meal.id == duplicate.id)
        ).scalar_one()
        warnings = [duplicate.analysis_warning] if duplicate.analysis_warning else []
        return to_response(duplicate, warnings, is_duplicate=True)

    raw_items = vision_service.analyze_food_image(raw_bytes)
    checked_items, warnings = meal_validation.apply_sanity_checks(raw_items)

    image_key = storage.save(
        raw_bytes, filename, folder=f"meals/user-{user.id}", content_type=content_type
    )
    total_calories = round(sum(i.approx_calories for i in checked_items), 1)

    meal = Meal(
        user_id=user.id,
        image_key=image_key,
        image_storage=storage.name,
        image_hash=image_hash,
        status=MEAL_STATUS_ANALYZED,
        total_calories=total_calories,
        analysis_raw_response=json.dumps([vars(i) for i in raw_items], default=str),
        analysis_warning="; ".join(warnings) if warnings else None,
        captured_at=datetime.now(UTC),
        created_by=user.id,
        updated_by=user.id,
    )
    meal.items = [
        MealItem(
            name=i.name,
            quantity_value=i.quantity_value,
            quantity_unit=i.quantity_unit,
            bbox_x1=i.bbox[0],
            bbox_y1=i.bbox[1],
            bbox_x2=i.bbox[2],
            bbox_y2=i.bbox[3],
            approx_calories=i.approx_calories,
            protein_g=i.protein_g,
            fat_g=i.fat_g,
            confidence=i.confidence,
            is_low_confidence=i.is_low_confidence,
            is_calorie_capped=i.is_calorie_capped,
            created_by=user.id,
            updated_by=user.id,
        )
        for i in checked_items
    ]

    db.add(meal)
    try:
        db.commit()
    except Exception:
        # Don't leave an orphan photo behind if the meal couldn't be saved.
        db.rollback()
        storage.delete(image_key)
        raise
    db.refresh(meal)

    return to_response(meal, warnings, is_duplicate=False)


def list_meals(
    db: Session, user: User, *, page: int, page_size: int, on_date: date | None = None
) -> list[Meal]:
    """Newest first. `on_date` keeps only meals eaten on that day in the user's timezone."""
    offset = (page - 1) * page_size
    query = (
        select(Meal)
        .options(selectinload(Meal.items), selectinload(Meal.weekly_menu))
        .where(Meal.user_id == user.id, Meal.deleted_at.is_(None))
    )
    if on_date is not None:
        start = datetime.combine(on_date, time.min, tzinfo=user_timezone(user))
        query = query.where(
            Meal.captured_at >= start.astimezone(UTC),
            Meal.captured_at < (start + timedelta(days=1)).astimezone(UTC),
        )
    return list(
        db.execute(
            query.order_by(Meal.captured_at.desc()).offset(offset).limit(page_size)
        ).scalars()
    )


def get_meal(db: Session, user: User, meal_id: int) -> Meal:
    meal = db.execute(
        select(Meal)
        .options(selectinload(Meal.items))
        .where(Meal.id == meal_id, Meal.user_id == user.id, Meal.deleted_at.is_(None))
    ).scalar_one_or_none()
    if meal is None:
        raise NotFoundError("Meal not found", code="meal_not_found")
    return meal


def _photo_storage(meal: Meal) -> StorageBackend | None:
    """The storage holding this meal's photo, or None if it has no photo."""
    if meal.image_key is None:
        return None
    # Meals saved before image_storage existed have their photo on local disk.
    return factory.get_storage(meal.image_storage or "local")


def meal_image_url(meal: Meal) -> str | None:
    """A temporary link to the photo (S3 presigned URL), or None when there's no
    photo or the storage can't make links (local disk: use GET /meals/{id}/image)."""
    storage = _photo_storage(meal)
    return storage.url_for(meal.image_key) if storage else None


def get_meal_image(db: Session, user: User, meal_id: int) -> tuple[bytes, str]:
    """The photo's bytes and content type, e.g. (b"...", "image/jpeg")."""
    meal = get_meal(db, user, meal_id)
    storage = _photo_storage(meal)
    if storage is None:
        raise NotFoundError("This meal has no photo", code="meal_image_not_found")
    try:
        content = storage.read(meal.image_key)
    except FileNotFoundError:
        raise NotFoundError("The photo file is missing", code="meal_image_not_found") from None
    content_type = mimetypes.guess_type(meal.image_key)[0] or "image/jpeg"
    return content, content_type


def delete_meal(db: Session, user: User, meal_id: int) -> None:
    """Soft-deletes for audit/history purposes: the row and its meal items stay in the
    database (marked deleted_at/deleted_by/is_active), only the stored photo is
    actually removed - "who deleted this, and when" remains queryable after this."""
    meal = get_meal(db, user, meal_id)
    storage = _photo_storage(meal)
    if storage is not None:
        storage.delete(meal.image_key)
    meal.deleted_at = datetime.now(UTC)
    meal.deleted_by = user.id
    meal.is_active = False
    db.commit()
