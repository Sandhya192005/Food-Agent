from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MealType


class SkipMealRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"meal_type": "breakfast"}})

    meal_type: MealType
    skip_date: date | None = Field(
        default=None, description="Local date of the skipped meal. Defaults to today."
    )


class SkippedMealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    skip_date: date
    meal_type: MealType
