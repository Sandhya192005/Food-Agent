from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import DAY_OF_WEEK_DISPLAY, DayOfWeek, MealType

if TYPE_CHECKING:
    from app.models.menu import WeeklyMenu, WeeklyMenuItem


class WeeklyMenuItemIn(BaseModel):
    name: str
    quantity_value: float = Field(gt=0)
    quantity_unit: str
    approx_calories: float = Field(ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)


class WeeklyMenuItemOut(BaseModel):
    id: int
    name: str
    quantity: str
    approx_calories: float
    protein_g: float | None
    fat_g: float | None

    @classmethod
    def from_model(cls, item: "WeeklyMenuItem") -> "WeeklyMenuItemOut":
        return cls(
            id=item.id,
            name=item.name,
            quantity=f"{item.quantity_value:g} {item.quantity_unit}",
            approx_calories=item.approx_calories,
            protein_g=item.protein_g,
            fat_g=item.fat_g,
        )


class WeeklyMenuIn(BaseModel):
    day_of_week: DayOfWeek
    meal_type: MealType
    label: str = Field(
        description="Short display name shown in the prompt, e.g. 'Sambar with Potato'"
    )
    items: list[WeeklyMenuItemIn] = Field(min_length=1)


class WeeklyMenuOut(BaseModel):
    id: int
    day_of_week: DayOfWeek
    day_name: str
    meal_type: MealType
    label: str
    total_calories: float
    items: list[WeeklyMenuItemOut]

    @classmethod
    def from_model(cls, menu: "WeeklyMenu") -> "WeeklyMenuOut":
        return cls(
            id=menu.id,
            day_of_week=menu.day_of_week,
            day_name=DAY_OF_WEEK_DISPLAY[menu.day_of_week],
            meal_type=menu.meal_type,
            label=menu.label,
            total_calories=round(sum(i.approx_calories for i in menu.items), 1),
            items=[WeeklyMenuItemOut.from_model(i) for i in menu.items],
        )


class MenuPromptOut(BaseModel):
    has_menu: bool
    day_name: str
    meal_type: MealType
    weekly_menu_id: int | None
    label: str | None
    question: str | None
    quick_actions: list[str]


class MenuConfirmRequest(BaseModel):
    """Pick the menu slot either by day + meal type, or by its weekly_menu_id
    (as returned by GET /menu/today-prompt)."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"day_of_week": "tuesday", "meal_type": "lunch"}}
    )

    day_of_week: DayOfWeek | None = None
    meal_type: MealType | None = None
    weekly_menu_id: int | None = None

    @model_validator(mode="after")
    def _require_slot(self) -> "MenuConfirmRequest":
        has_day_slot = self.day_of_week is not None and self.meal_type is not None
        if self.weekly_menu_id is None and not has_day_slot:
            raise ValueError("Provide day_of_week and meal_type, or weekly_menu_id")
        return self
