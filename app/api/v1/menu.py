from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_current_user
from app.core.constants import DayOfWeek, MealType
from app.db.session import get_db
from app.models.user import User
from app.schemas.menu import MenuPromptOut, WeeklyMenuIn, WeeklyMenuOut
from app.services import menu_service

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get(
    "/weekly",
    response_model=list[WeeklyMenuOut],
    summary="Get the full recurring office weekly menu",
)
def get_weekly_menu(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeeklyMenuOut]:
    menus = menu_service.get_week_menu(db)
    return [WeeklyMenuOut.from_model(m) for m in menus]


@router.get(
    "/weekly/{day_of_week}",
    response_model=list[WeeklyMenuOut],
    summary="Get the office menu for one day of the week",
    description="Returns every meal slot (breakfast, lunch, dinner, snack) set for that "
    "day. Returns an empty list if nothing is set for the day.",
)
def get_day_menu(
    day_of_week: DayOfWeek,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WeeklyMenuOut]:
    menus = menu_service.get_day_menu(db, day_of_week)
    return [WeeklyMenuOut.from_model(m) for m in menus]


@router.put(
    "/weekly",
    response_model=WeeklyMenuOut,
    summary="Set or replace a day's menu slot (admin only)",
    description="Upserts by (day_of_week, meal_type) — calling this again for the "
    "same day+meal_type replaces its food items.",
)
def set_weekly_menu(
    payload: WeeklyMenuIn,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> WeeklyMenuOut:
    menu = menu_service.create_or_replace_menu(db, admin, payload)
    return WeeklyMenuOut.from_model(menu)


@router.delete(
    "/weekly/{weekly_menu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a day's menu slot (admin only)",
)
def delete_weekly_menu(
    weekly_menu_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> None:
    menu_service.delete_menu_entry(db, weekly_menu_id)


@router.get(
    "/today-prompt",
    response_model=MenuPromptOut,
    summary="Check whether today's meal matches the recurring office menu",
    description="Intended to be polled by the client around meal times, similar to "
    "the water reminder. If meal_type is omitted, it's inferred from the current "
    "local hour. When has_menu is true and the user taps Yes, call "
    "POST /meals/confirm-from-menu with the returned weekly_menu_id instead of "
    "uploading a photo; on No, fall back to the normal POST /meals/analyze upload.",
)
def today_prompt(
    meal_type: MealType | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MenuPromptOut:
    return menu_service.get_today_prompt(db, current_user, meal_type)
