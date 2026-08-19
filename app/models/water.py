from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin, utcnow


class WaterLog(TimestampMixin, AuditMixin, Base):
    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    user: Mapped["User"] = relationship(back_populates="water_logs")  # noqa: F821


class WaterReminderSnooze(TimestampMixin, AuditMixin, Base):
    __tablename__ = "water_reminder_snoozes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    snoozed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="water_reminder_snooze")  # noqa: F821
