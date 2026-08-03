from typing import Literal

from pydantic import BaseModel, Field


class WaterLogRequest(BaseModel):
    amount_ml: int | None = Field(default=None, gt=0, le=5000)
    source: Literal["quick_yes", "custom_amount"] = "quick_yes"

    def resolved_amount_ml(self, default_ml: int) -> int:
        if self.amount_ml is not None:
            return self.amount_ml
        return default_ml


class WaterLogOut(BaseModel):
    id: int
    amount_ml: int
    source: str

    model_config = {"from_attributes": True}


class WaterTodayOut(BaseModel):
    consumed_ml: int
    goal_ml: int
    percent: float
    remaining_ml: int


class WaterReminderOut(BaseModel):
    should_remind: bool
    reason: str
    message: str | None
    minutes_since_last: int
    quick_actions: list[str]
