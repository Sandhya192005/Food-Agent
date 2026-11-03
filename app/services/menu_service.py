import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    DAY_OF_WEEK_BY_INDEX,
    DAY_OF_WEEK_DISPLAY,
    MEAL_SOURCE_MENU_TEMPLATE,
    MEAL_STATUS_ANALYZED,
    DayOfWeek,
    MealType,
    meal_type_for_time,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.meal import Meal, MealItem
from app.models.menu import WeeklyMenu, WeeklyMenuItem
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse
from app.schemas.menu import MenuConfirmRequest, MenuPromptOut, WeeklyMenuIn
from app.services import meal_service, meal_validation, skipped_meal_service
from app.services.meal_validation import RawFoodItem
from app.services.timezone_utils import user_timezone


def _get_menu_with_items(db: Session, weekly_menu_id: int) -> WeeklyMenu:
    menu = db.execute(
        select(WeeklyMenu)
        .options(selectinload(WeeklyMenu.items))
        .where(WeeklyMenu.id == weekly_menu_id)
    ).scalar_one_or_none()
    if menu is None:
        raise NotFoundError("Menu entry not found", code="menu_not_found")
    return menu


def get_menu_for_slot(db: Session, day_of_week: DayOfWeek, meal_type: MealType) -> WeeklyMenu:
    menu = db.execute(
        select(WeeklyMenu)
        .options(selectinload(WeeklyMenu.items))
        .where(WeeklyMenu.day_of_week == day_of_week, WeeklyMenu.meal_type == meal_type)
    ).scalar_one_or_none()
    if menu is None:
        raise NotFoundError(
            f"No {meal_type.value} menu set for {DAY_OF_WEEK_DISPLAY[day_of_week]}",
            code="menu_not_found",
        )
    return menu


def get_week_menu(db: Session) -> list[WeeklyMenu]:
    return list(
        db.execute(
            select(WeeklyMenu)
            .options(selectinload(WeeklyMenu.items))
            .order_by(WeeklyMenu.day_of_week, WeeklyMenu.meal_type)
        ).scalars()
    )


def get_day_menu(db: Session, day_of_week: DayOfWeek) -> list[WeeklyMenu]:
    menus = db.execute(
        select(WeeklyMenu)
        .options(selectinload(WeeklyMenu.items))
        .where(WeeklyMenu.day_of_week == day_of_week)
    ).scalars()
    # Breakfast → lunch → dinner → snack, regardless of how the DB sorts enums.
    meal_order = list(MealType)
    return sorted(menus, key=lambda m: meal_order.index(m.meal_type))


def create_or_replace_menu(db: Session, admin: User, payload: WeeklyMenuIn) -> WeeklyMenu:
    """Upserts by (day_of_week, meal_type): replaces the item list if an entry for
    that slot already exists, since there's only ever one menu per day+meal_type."""
    existing = db.execute(
        select(WeeklyMenu)
        .options(selectinload(WeeklyMenu.items))
        .where(
            WeeklyMenu.day_of_week == payload.day_of_week,
            WeeklyMenu.meal_type == payload.meal_type,
        )
    ).scalar_one_or_none()

    if existing is None:
        menu = WeeklyMenu(
            day_of_week=payload.day_of_week,
            meal_type=payload.meal_type,
            label=payload.label,
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(menu)
    else:
        menu = existing
        menu.label = payload.label
        menu.updated_by = admin.id

    menu.items = [
        WeeklyMenuItem(
            name=item.name,
            quantity_value=item.quantity_value,
            quantity_unit=item.quantity_unit,
            approx_calories=item.approx_calories,
            protein_g=item.protein_g,
            fat_g=item.fat_g,
            created_by=admin.id,
            updated_by=admin.id,
        )
        for item in payload.items
    ]

    db.commit()
    db.refresh(menu)
    return menu


def delete_menu_entry(db: Session, weekly_menu_id: int) -> None:
    menu = _get_menu_with_items(db, weekly_menu_id)
    db.delete(menu)
    db.commit()


def _infer_meal_type(now_local: datetime) -> MealType:
    return meal_type_for_time(now_local.time())


def get_today_prompt(db: Session, user: User, meal_type: MealType | None) -> MenuPromptOut:
    now_local = datetime.now(user_timezone(user))
    resolved_meal_type = meal_type or _infer_meal_type(now_local)
    day_of_week = DAY_OF_WEEK_BY_INDEX[now_local.weekday()]
    day_name = DAY_OF_WEEK_DISPLAY[day_of_week]

    menu = db.execute(
        select(WeeklyMenu)
        .options(selectinload(WeeklyMenu.items))
        .where(
            WeeklyMenu.day_of_week == day_of_week,
            WeeklyMenu.meal_type == resolved_meal_type,
        )
    ).scalar_one_or_none()

    if menu is None:
        return MenuPromptOut(
            has_menu=False,
            day_name=day_name,
            meal_type=resolved_meal_type,
            weekly_menu_id=None,
            label=None,
            question="No scheduled meal right now",
            quick_actions=[],
        )

    question = f"Today is {day_name}, is your {resolved_meal_type.value} going to be {menu.label}?"
    return MenuPromptOut(
        has_menu=True,
        day_name=day_name,
        meal_type=resolved_meal_type,
        weekly_menu_id=menu.id,
        label=menu.label,
        question=question,
        quick_actions=["yes", "no"],
    )


# How far back a missed meal can be logged, and clock skew allowed for "now".
MAX_BACKDATE = timedelta(days=7)
FUTURE_GRACE = timedelta(minutes=5)


def _resolve_eaten_at(user: User, menu: WeeklyMenu, eaten_at: datetime | None) -> datetime:
    now = datetime.now(UTC)
    if eaten_at is None:
        return now
    tz = user_timezone(user)
    if eaten_at.tzinfo is None:
        eaten_at = eaten_at.replace(tzinfo=tz)
    eaten_at = eaten_at.astimezone(UTC)
    if eaten_at > now + FUTURE_GRACE:
        raise ValidationError("eaten_at can't be in the future", code="eaten_at_in_future")
    if eaten_at < now - MAX_BACKDATE:
        raise ValidationError("Meals can only be logged up to 7 days back", code="eaten_at_too_old")
    local_day = DAY_OF_WEEK_BY_INDEX[eaten_at.astimezone(tz).weekday()]
    if local_day != menu.day_of_week:
        raise ValidationError(
            f"eaten_at is a {DAY_OF_WEEK_DISPLAY[local_day]}, but this menu is for "
            f"{DAY_OF_WEEK_DISPLAY[menu.day_of_week]}",
            code="eaten_at_day_mismatch",
        )
    return eaten_at


def confirm_meal_from_menu(
    db: Session, user: User, payload: MenuConfirmRequest
) -> MealAnalyzeResponse:
    if payload.weekly_menu_id is not None:
        menu = _get_menu_with_items(db, payload.weekly_menu_id)
    else:
        assert payload.day_of_week is not None and payload.meal_type is not None
        menu = get_menu_for_slot(db, payload.day_of_week, payload.meal_type)
    captured_at = _resolve_eaten_at(user, menu, payload.eaten_at)
    skipped_meal_service.clear_skip(
        db, user, captured_at.astimezone(user_timezone(user)).date(), menu.meal_type
    )

    raw_items = [
        RawFoodItem(
            name=item.name,
            quantity_value=item.quantity_value,
            quantity_unit=item.quantity_unit,
            bbox=None,
            approx_calories=item.approx_calories,
            confidence=1.0,
            protein_g=item.protein_g,
            fat_g=item.fat_g,
        )
        for item in menu.items
    ]
    checked_items, warnings = meal_validation.apply_sanity_checks(raw_items)
    total_calories = round(sum(i.approx_calories for i in checked_items), 1)

    meal = Meal(
        user_id=user.id,
        image_key=None,
        image_hash=None,
        source=MEAL_SOURCE_MENU_TEMPLATE,
        weekly_menu_id=menu.id,
        status=MEAL_STATUS_ANALYZED,
        total_calories=total_calories,
        analysis_raw_response=json.dumps({"weekly_menu_id": menu.id, "label": menu.label}),
        analysis_warning="; ".join(warnings) if warnings else None,
        captured_at=captured_at,
        created_by=user.id,
        updated_by=user.id,
    )
    meal.items = [
        MealItem(
            name=i.name,
            quantity_value=i.quantity_value,
            quantity_unit=i.quantity_unit,
            bbox_x1=i.bbox[0] if i.bbox else None,
            bbox_y1=i.bbox[1] if i.bbox else None,
            bbox_x2=i.bbox[2] if i.bbox else None,
            bbox_y2=i.bbox[3] if i.bbox else None,
            approx_calories=i.approx_calories,
            protein_g=i.protein_g,
            fat_g=i.fat_g,
            confidence=i.confidence,
            is_low_confidence=i.is_low_confidence,
            is_calorie_capped=i.is_calorie_capped,
            created_by=user.id,
            updated_by=user.id,
        )
        for i in checked_items
    ]

    db.add(meal)
    db.commit()
    db.refresh(meal)

    return meal_service.to_response(meal, warnings, is_duplicate=False)
