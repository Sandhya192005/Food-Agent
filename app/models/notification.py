from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import NotificationStatus, NotificationType
from app.db.base import AuditMixin, Base, TimestampMixin


class Notification(TimestampMixin, AuditMixin, Base):
    """A proactive nudge created by a scheduler-driven agent (meal or water), not by
    a user request. Distinct from WaterReminderSnooze/the on-demand /water/reminder
    and /menu/today-prompt endpoints, which are pulled by the client instead of
    pushed by a background job."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus), nullable=False, default=NotificationStatus.PENDING
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()  # noqa: F821
