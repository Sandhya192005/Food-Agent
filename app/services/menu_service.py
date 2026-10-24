import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    DAY_OF_WEEK_BY_INDEX,
    DAY_OF_WEEK_DISPLAY,
    MEAL_SOURCE_MENU_TEMPLATE,
    MEAL_STATUS_ANALYZED,
    MEAL_TYPE_TIME_RANGES,
    DayOfWeek,
    MealType,
)
from app.core.exceptions import NotFoundError
from app.models.meal import Meal, MealItem
from app.models.menu import WeeklyMenu, WeeklyMenuItem
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse
from app.schemas.menu import MenuPromptOut, WeeklyMenuIn
from app.services import meal_service, meal_validation
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
    current_time = now_local.time()
    for meal_type, start, end in MEAL_TYPE_TIME_RANGES:
        if start <= current_time < end:
            return meal_type
    return MealType.SNACK


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

    question = (
        f"Today is {day_name}, is your {resolved_meal_type.value} going to be {menu.label}?"
    )
    return MenuPromptOut(
        has_menu=True,
        day_name=day_name,
        meal_type=resolved_meal_type,
        weekly_menu_id=menu.id,
        label=menu.label,
        question=question,
        quick_actions=["yes", "no"],
    )


def confirm_meal_from_menu(db: Session, user: User, weekly_menu_id: int) -> MealAnalyzeResponse:
    menu = _get_menu_with_items(db, weekly_menu_id)

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
        image_path=None,
        image_hash=None,
        source=MEAL_SOURCE_MENU_TEMPLATE,
        weekly_menu_id=menu.id,
        status=MEAL_STATUS_ANALYZED,
        total_calories=total_calories,
        analysis_raw_response=json.dumps(
            {"weekly_menu_id": menu.id, "label": menu.label}
        ),
        analysis_warning="; ".join(warnings) if warnings else None,
        captured_at=datetime.now(UTC),
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
