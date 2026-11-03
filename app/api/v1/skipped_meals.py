from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.skipped_meal import SkipMealRequest, SkippedMealOut
from app.services import skipped_meal_service

router = APIRouter(prefix="/skipped-meals", tags=["meals"])


@router.post(
    "",
    response_model=SkippedMealOut,
    status_code=status.HTTP_201_CREATED,
    summary="Skip a meal",
    description="Marks breakfast, lunch or dinner as skipped for a day (today by default). "
    "Nothing is added to meal history. Logging that meal later clears the skip.",
)
def skip_meal(
    payload: SkipMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkippedMealOut:
    skipped = skipped_meal_service.skip_meal(db, current_user, payload.meal_type, payload.skip_date)
    return SkippedMealOut.model_validate(skipped)


@router.get("", response_model=list[SkippedMealOut], summary="List skipped meals for a day")
def list_skipped_meals(
    on_date: date | None = Query(
        default=None, alias="date", description="YYYY-MM-DD in your timezone; defaults to today"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SkippedMealOut]:
    return [
        SkippedMealOut.model_validate(s)
        for s in skipped_meal_service.list_skipped(db, current_user, on_date)
    ]


@router.delete("/{skip_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Undo a skipped meal")
def undo_skip(
    skip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    skipped_meal_service.undo_skip(db, current_user, skip_id)
