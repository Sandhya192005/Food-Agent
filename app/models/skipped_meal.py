from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import MealType
from app.db.base import AuditMixin, Base, TimestampMixin


class SkippedMeal(TimestampMixin, AuditMixin, Base):
    """A meal the user chose to skip on a given day. Kept apart from `meals` so a
    skip never shows up in meal history or calorie totals."""

    __tablename__ = "skipped_meals"
    __table_args__ = (
        UniqueConstraint("user_id", "skip_date", "meal_type", name="uq_skipped_meal_user_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The user's local date the meal belonged to.
    skip_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[MealType] = mapped_column(SAEnum(MealType), nullable=False)
