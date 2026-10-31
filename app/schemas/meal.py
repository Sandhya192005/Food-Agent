from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.core.constants import MealType, meal_type_for_time

if TYPE_CHECKING:
    from app.models.meal import Meal, MealItem


def _format_grams(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:g} g"


class MealItemOut(BaseModel):
    name: str
    bounding_box: list[float] | None
    quantity: str
    approx_cal: float
    protein: str | None = None
    fat: str | None = None
    confidence: float | None = None
    is_low_confidence: bool = False
    is_calorie_capped: bool = False

    @classmethod
    def from_model(cls, item: "MealItem") -> "MealItemOut":
        bounding_box = (
            [item.bbox_x1, item.bbox_y1, item.bbox_x2, item.bbox_y2]
            if item.bbox_x1 is not None
            else None
        )
        return cls(
            name=item.name,
            bounding_box=bounding_box,
            quantity=f"{item.quantity_value:g} {item.quantity_unit}",
            approx_cal=item.approx_calories,
            protein=_format_grams(item.protein_g),
            fat=_format_grams(item.fat_g),
            confidence=item.confidence,
            is_low_confidence=item.is_low_confidence,
            is_calorie_capped=item.is_calorie_capped,
        )


class MealAnalyzeResponse(BaseModel):
    meal_id: int
    is_duplicate: bool
    total_calories: float
    items: list[MealItemOut]
    warnings: list[str]
    source: str = "photo"


def _meal_title(meal: "Meal") -> str | None:
    """The office menu's name, or the first food items, e.g. "Rice, Dal +2 more"."""
    if meal.weekly_menu is not None:
        return meal.weekly_menu.label
    names = [item.name for item in meal.items]
    if not names:
        return None
    title = ", ".join(names[:2])
    return f"{title} +{len(names) - 2} more" if len(names) > 2 else title


def _meal_type(meal: "Meal", timezone: ZoneInfo | None) -> MealType:
    if meal.weekly_menu is not None:
        return meal.weekly_menu.meal_type
    captured = meal.captured_at
    if captured.tzinfo is None:  # SQLite returns naive UTC
        captured = captured.replace(tzinfo=UTC)
    return meal_type_for_time(captured.astimezone(timezone or UTC).time())


class MealSummaryOut(BaseModel):
    id: int
    total_calories: float | None
    status: str
    source: str
    weekly_menu_id: int | None = None
    meal_type: MealType = Field(
        description="From the office menu, or from the time eaten (user's timezone)"
    )
    title: str | None = Field(default=None, description="Office menu name, or the first food items")
    captured_at: datetime
    warnings: list[str]

    @classmethod
    def from_model(cls, meal: "Meal", timezone: ZoneInfo | None = None) -> "MealSummaryOut":
        return cls(
            id=meal.id,
            total_calories=meal.total_calories,
            status=meal.status,
            source=meal.source,
            weekly_menu_id=meal.weekly_menu_id,
            meal_type=_meal_type(meal, timezone),
            title=_meal_title(meal),
            captured_at=meal.captured_at,
            warnings=[meal.analysis_warning] if meal.analysis_warning else [],
        )


class MealDetailOut(MealSummaryOut):
    items: list[MealItemOut]
    has_image: bool = Field(default=False, description="True for meals logged with a photo")
    image_url: str | None = Field(
        default=None,
        description="Temporary link to the photo (S3 presigned URL, expires in a few "
        "minutes). Null when the photo is on local disk: fetch GET /meals/{id}/image instead.",
    )

    @classmethod
    def from_model(
        cls, meal: "Meal", timezone: ZoneInfo | None = None, *, image_url: str | None = None
    ) -> "MealDetailOut":
        summary = MealSummaryOut.from_model(meal, timezone)
        return cls(
            **summary.model_dump(),
            items=[MealItemOut.from_model(item) for item in meal.items],
            has_image=meal.image_key is not None,
            image_url=image_url,
        )
