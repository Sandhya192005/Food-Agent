from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DayOfWeek, MealType
from app.db.base import AuditMixin, Base, TimestampMixin


class WeeklyMenu(TimestampMixin, AuditMixin, Base):
    """One recurring office meal slot, e.g. 'Tuesday lunch'. Shared across all
    users - not tied to a specific user_id - and maintained by admins only."""

    __tablename__ = "weekly_menus"
    __table_args__ = (
        UniqueConstraint("day_of_week", "meal_type", name="uq_weekly_menu_day_mealtype"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_of_week: Mapped[DayOfWeek] = mapped_column(SAEnum(DayOfWeek), nullable=False)
    meal_type: Mapped[MealType] = mapped_column(SAEnum(MealType), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    items: Mapped[list["WeeklyMenuItem"]] = relationship(
        back_populates="menu", cascade="all, delete-orphan"
    )


class WeeklyMenuItem(TimestampMixin, AuditMixin, Base):
    __tablename__ = "weekly_menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekly_menu_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_menus.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_value: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    approx_calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    menu: Mapped["WeeklyMenu"] = relationship(back_populates="items")
