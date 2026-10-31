from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MEAL_SOURCE_PHOTO
from app.db.base import AuditMixin, Base, TimestampMixin, utcnow


class Meal(TimestampMixin, AuditMixin, Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Where the photo is stored: the object key (S3) or file name (local), plus
    # which storage holds it ("local" or "s3"). Both null for meals logged from a
    # weekly menu template (source="menu_template"), since there's no photo.
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_storage: Mapped[str | None] = mapped_column(String(10), nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    source: Mapped[str] = mapped_column(String(20), nullable=False, default=MEAL_SOURCE_PHOTO)
    weekly_menu_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_menus.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_warning: Mapped[str | None] = mapped_column(String(255), nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="meals")  # noqa: F821
    weekly_menu: Mapped["WeeklyMenu | None"] = relationship(viewonly=True)  # noqa: F821
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealItem(TimestampMixin, AuditMixin, Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meal_id: Mapped[int] = mapped_column(
        ForeignKey("meals.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_value: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Null for items from a menu-confirmed meal (source="menu_template"), since
    # there's no photo to have detected a bounding box in.
    bbox_x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y2: Mapped[float | None] = mapped_column(Float, nullable=True)

    approx_calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_low_confidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_calorie_capped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    meal: Mapped["Meal"] = relationship(back_populates="items")
