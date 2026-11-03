from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationRespondRequest
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/pending",
    response_model=list[NotificationOut],
    summary="List this user's unanswered proactive nudges",
    description="Meal-nudge and water-check notifications raised by the background "
    "agents (app/services/notification_service.py) that haven't been answered yet. "
    "Intended to be polled by the client, since there is no push delivery wired up "
    "yet — see ARCHITECTURE.md.",
)
def list_pending_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    notifications = notification_service.list_pending(db, current_user)
    return [NotificationOut.from_model(n) for n in notifications]


@router.post(
    "/{notification_id}/respond",
    response_model=NotificationOut,
    summary="Answer a pending notification",
    description="Answering 'yes' on a water-check notification logs 250ml of water "
    "automatically. Answering 'no' on a water-check schedules a faster retry "
    "(WATER_RETRY_AFTER_NO_MINUTES) instead of waiting for the normal threshold.",
)
def respond_to_notification(
    notification_id: int,
    payload: NotificationRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    notification = notification_service.respond_to_notification(
        db, current_user, notification_id, payload.response
    )
    return NotificationOut.from_model(notification)
