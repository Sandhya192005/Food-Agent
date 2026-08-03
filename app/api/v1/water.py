from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.water import (
    WaterLogOut,
    WaterLogRequest,
    WaterReminderOut,
    WaterTodayOut,
)
from app.services import water_service

router = APIRouter(prefix="/water", tags=["water"])


@router.post(
    "/log",
    response_model=WaterLogOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a water intake entry",
    description="Defaults to 250ml when amount_ml is omitted with source=quick_yes. "
    "Clears any active reminder snooze.",
)
def log_water(
    payload: WaterLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaterLogOut:
    water_log = water_service.log_water(db, current_user, payload)
    return WaterLogOut.model_validate(water_log)


@router.get(
    "/today",
    response_model=WaterTodayOut,
    summary="Get today's hydration progress",
    description="Consumed/goal/remaining for the current calendar day in the user's timezone.",
)
def water_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaterTodayOut:
    return water_service.get_today_summary(db, current_user)


@router.get(
    "/reminder",
    response_model=WaterReminderOut,
    summary="Check whether a hydration reminder should be shown",
    description="Intended to be polled periodically by the client. Returns "
    "should_remind based on time since the last log, respecting any active snooze.",
)
def water_reminder(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WaterReminderOut:
    return water_service.get_reminder_status(db, current_user)


@router.post(
    "/snooze",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Snooze the hydration reminder",
    description="Called when the user taps 'Remind Me Later'.",
)
def snooze_water_reminder(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    water_service.snooze_reminder(db, current_user)
