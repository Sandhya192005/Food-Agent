import hashlib
import io
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.db.base import ensure_utc
from app.models.meal import Meal


@dataclass
class RawFoodItem:
    name: str
    quantity_value: float
    quantity_unit: str
    bbox: tuple[float, float, float, float]
    approx_calories: float
    confidence: float | None
    protein_g: float | None = None
    fat_g: float | None = None


@dataclass
class CheckedFoodItem(RawFoodItem):
    is_low_confidence: bool = False
    is_calorie_capped: bool = False


def validate_content_type(content_type: str | None) -> None:
    if content_type not in settings.allowed_image_types:
        allowed = ", ".join(settings.allowed_image_types)
        raise ValidationError(
            f"Unsupported image type '{content_type}'. Allowed types: {allowed}",
            code="unsupported_image_type",
        )


def validate_size(size_bytes: int) -> None:
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationError(
            f"Image exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit",
            code="image_too_large",
            status_code=413,
        )


def validate_image_bytes(raw_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Uploaded file is not a valid image", code="corrupt_image") from exc


def compute_image_hash(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def find_recent_duplicate(db: Session, user_id: int, image_hash: str) -> Meal | None:
    window_start = datetime.now(UTC) - timedelta(
        minutes=settings.DUPLICATE_UPLOAD_WINDOW_MINUTES
    )
    candidate = db.execute(
        select(Meal)
        .where(Meal.user_id == user_id, Meal.image_hash == image_hash)
        .order_by(Meal.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if candidate is not None and ensure_utc(candidate.created_at) >= window_start:
        return candidate
    return None


def apply_sanity_checks(items: list[RawFoodItem]) -> tuple[list[CheckedFoodItem], list[str]]:
    """Clamps implausible per-item/per-meal calorie estimates and flags low-confidence
    items. Never drops items — flagged data is still returned/persisted, per spec."""
    warnings: list[str] = []
    checked_items: list[CheckedFoodItem] = []

    for item in items:
        calories = item.approx_calories
        capped = False
        if calories > settings.MAX_ITEM_CALORIES:
            calories = settings.MAX_ITEM_CALORIES
            capped = True
        elif calories < 0:
            calories = 0
            capped = True

        low_confidence = (
            item.confidence is not None and item.confidence < settings.LOW_CONFIDENCE_THRESHOLD
        )

        checked_items.append(
            CheckedFoodItem(
                **vars(replace(item, approx_calories=calories)),
                is_low_confidence=low_confidence,
                is_calorie_capped=capped,
            )
        )

    total_calories = sum(i.approx_calories for i in checked_items)
    if total_calories > settings.MAX_MEAL_CALORIES:
        scale = settings.MAX_MEAL_CALORIES / total_calories if total_calories else 0
        for item in checked_items:
            item.approx_calories = round(item.approx_calories * scale, 1)
            item.is_calorie_capped = True
        warnings.append("Total calorie estimate was unrealistically high and has been capped")

    capped_count = sum(1 for i in checked_items if i.is_calorie_capped)
    low_confidence_count = sum(1 for i in checked_items if i.is_low_confidence)

    if capped_count:
        warnings.append(
            f"{capped_count} item(s) had an implausible calorie estimate and were capped"
        )
    if low_confidence_count:
        warnings.append(
            f"{low_confidence_count} item(s) detected with low confidence — please verify"
        )

    return checked_items, warnings
