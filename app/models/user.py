from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ActivityLevel, DietPreference, Gender, Goal
from app.db.base import AuditMixin, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.meal import Meal
    from app.models.recommendation import RecommendationLog
    from app.models.water import WaterLog, WaterReminderSnooze

user_medical_conditions = Table(
    "user_medical_conditions",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "medical_condition_id",
        ForeignKey("medical_conditions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(TimestampMixin, AuditMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    preferred_name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Gender] = mapped_column(SAEnum(Gender), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)

    goal: Mapped[Goal] = mapped_column(SAEnum(Goal), nullable=False)
    diet_preference: Mapped[DietPreference] = mapped_column(SAEnum(DietPreference), nullable=False)
    activity_level: Mapped[ActivityLevel] = mapped_column(SAEnum(ActivityLevel), nullable=False)

    daily_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmr: Mapped[float | None] = mapped_column(Float, nullable=True)
    tdee: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_water_goal_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    medical_conditions: Mapped[list["MedicalCondition"]] = relationship(
        secondary=user_medical_conditions, back_populates="users"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    meals: Mapped[list["Meal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    water_logs: Mapped[list["WaterLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    water_reminder_snooze: Mapped["WaterReminderSnooze | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    recommendation_logs: Mapped[list["RecommendationLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class MedicalCondition(TimestampMixin, AuditMixin, Base):
    __tablename__ = "medical_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    users: Mapped[list["User"]] = relationship(
        secondary=user_medical_conditions, back_populates="medical_conditions"
    )


class RefreshToken(TimestampMixin, AuditMixin, Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
