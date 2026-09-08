from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.models.notification import Notification


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str
    status: str
    created_at: datetime
    quick_actions: list[str]

    @classmethod
    def from_model(cls, notification: "Notification") -> "NotificationOut":
        return cls(
            id=notification.id,
            type=notification.type.value,
            message=notification.message,
            status=notification.status.value,
            created_at=notification.created_at,
            quick_actions=["yes", "no"] if notification.status.value == "pending" else [],
        )


class NotificationRespondRequest(BaseModel):
    response: Literal["yes", "no"]
