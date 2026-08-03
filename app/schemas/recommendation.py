import json
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.recommendation import RecommendationLog


class MealSuggestionOut(BaseModel):
    name: str
    reason: str
    est_cost: float
    est_calories: float


class RecommendationOut(BaseModel):
    summary: str
    meal_suggestions: list[MealSuggestionOut]
    hydration_tip: str
    warnings: list[str]


class RecommendationHistoryEntryOut(BaseModel):
    id: int
    created_at: datetime
    recommendation: RecommendationOut

    @classmethod
    def from_model(cls, log: "RecommendationLog") -> "RecommendationHistoryEntryOut":
        return cls(
            id=log.id,
            created_at=log.created_at,
            recommendation=RecommendationOut.model_validate(json.loads(log.response_json)),
        )
