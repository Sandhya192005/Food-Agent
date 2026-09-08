import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import MEAL_STATUS_ANALYZED
from app.core.exceptions import NotFoundError
from app.models.meal import Meal, MealItem
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse, MealItemOut
from app.services import meal_validation
from app.services.ai import vision_service
from app.services.storage.base import StorageBackend


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

    image_path = storage.save(raw_bytes, filename)
    total_calories = round(sum(i.approx_calories for i in checked_items), 1)

    meal = Meal(
        user_id=user.id,
        image_path=image_path,
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
    db.commit()
    db.refresh(meal)

    return to_response(meal, warnings, is_duplicate=False)


def list_meals(
    db: Session, user: User, *, page: int, page_size: int
) -> list[Meal]:
    offset = (page - 1) * page_size
    return list(
        db.execute(
            select(Meal)
            .where(Meal.user_id == user.id, Meal.deleted_at.is_(None))
            .order_by(Meal.captured_at.desc())
            .offset(offset)
            .limit(page_size)
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


def delete_meal(db: Session, user: User, storage: StorageBackend, meal_id: int) -> None:
    """Soft-deletes for audit/history purposes: the row and its meal items stay in the
    database (marked deleted_at/deleted_by/is_active), only the stored image file is
    actually removed - "who deleted this, and when" remains queryable after this."""
    meal = get_meal(db, user, meal_id)
    if meal.image_path is not None:
        storage.delete(meal.image_path)
    meal.deleted_at = datetime.now(UTC)
    meal.deleted_by = user.id
    meal.is_active = False
    db.commit()
