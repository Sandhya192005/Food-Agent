from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.meal import Meal, MealItem


def _format_grams(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value:g} g"


class MealItemOut(BaseModel):
    name: str
    bounding_box: list[float]
    quantity: str
    approx_cal: float
    protein: str | None = None
    fat: str | None = None
    confidence: float | None = None
    is_low_confidence: bool = False
    is_calorie_capped: bool = False

    @classmethod
    def from_model(cls, item: "MealItem") -> "MealItemOut":
        return cls(
            name=item.name,
            bounding_box=[item.bbox_x1, item.bbox_y1, item.bbox_x2, item.bbox_y2],
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


class MealSummaryOut(BaseModel):
    id: int
    total_calories: float | None
    status: str
    captured_at: datetime
    warnings: list[str]

    @classmethod
    def from_model(cls, meal: "Meal") -> "MealSummaryOut":
        return cls(
            id=meal.id,
            total_calories=meal.total_calories,
            status=meal.status,
            captured_at=meal.captured_at,
            warnings=[meal.analysis_warning] if meal.analysis_warning else [],
        )


class MealDetailOut(MealSummaryOut):
    items: list[MealItemOut]

    @classmethod
    def from_model(cls, meal: "Meal") -> "MealDetailOut":
        summary = MealSummaryOut.from_model(meal)
        return cls(
            **summary.model_dump(),
            items=[MealItemOut.from_model(item) for item in meal.items],
        )
