from typing import TYPE_CHECKING

from pydantic import BaseModel, EmailStr, Field

from app.core.constants import ActivityLevel, DietPreference, Gender, Goal

if TYPE_CHECKING:
    from app.models.user import User


class UserProfileBase(BaseModel):
    preferred_name: str = Field(
        ..., min_length=1, max_length=100, description="What should I call you?"
    )
    age: int = Field(..., ge=1, le=120)
    gender: Gender
    height_cm: float = Field(..., gt=0, le=300)
    weight_kg: float = Field(..., gt=0, le=500)
    medical_conditions: list[str] = Field(default_factory=list)
    goal: Goal
    diet_preference: DietPreference
    activity_level: ActivityLevel
    daily_budget: float | None = Field(default=None, ge=0)
    monthly_budget: float | None = Field(default=None, ge=0)
    timezone: str = Field(default="UTC", description="IANA timezone, e.g. Asia/Kolkata")


class SignupRequest(UserProfileBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdateRequest(BaseModel):
    preferred_name: str | None = Field(default=None, min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=1, le=120)
    gender: Gender | None = None
    height_cm: float | None = Field(default=None, gt=0, le=300)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    medical_conditions: list[str] | None = None
    goal: Goal | None = None
    diet_preference: DietPreference | None = None
    activity_level: ActivityLevel | None = None
    daily_budget: float | None = Field(default=None, ge=0)
    monthly_budget: float | None = Field(default=None, ge=0)
    timezone: str | None = None


class HealthMetricsOut(BaseModel):
    bmi: float | None
    bmr: float | None
    tdee: float | None
    daily_water_goal_ml: int | None


class UserRead(BaseModel):
    id: int
    email: EmailStr
    preferred_name: str
    age: int
    gender: Gender
    height_cm: float
    weight_kg: float
    medical_conditions: list[str]
    goal: Goal
    diet_preference: DietPreference
    activity_level: ActivityLevel
    daily_budget: float | None
    monthly_budget: float | None
    currency: str = "INR"
    timezone: str
    metrics: HealthMetricsOut

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, user: "User") -> "UserRead":
        return cls(
            id=user.id,
            email=user.email,
            preferred_name=user.preferred_name,
            age=user.age,
            gender=user.gender,
            height_cm=user.height_cm,
            weight_kg=user.weight_kg,
            medical_conditions=sorted(mc.name for mc in user.medical_conditions),
            goal=user.goal,
            diet_preference=user.diet_preference,
            activity_level=user.activity_level,
            daily_budget=user.daily_budget,
            monthly_budget=user.monthly_budget,
            timezone=user.timezone,
            metrics=HealthMetricsOut(
                bmi=user.bmi,
                bmr=user.bmr,
                tdee=user.tdee,
                daily_water_goal_ml=user.daily_water_goal_ml,
            ),
        )
