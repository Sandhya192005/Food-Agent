from datetime import date

from fastapi import APIRouter, Depends, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse, MealDetailOut, MealSummaryOut
from app.schemas.menu import MenuConfirmRequest
from app.services import meal_service, menu_service
from app.services.storage.base import StorageBackend
from app.services.storage.local import get_storage_backend
from app.services.timezone_utils import user_timezone

router = APIRouter(prefix="/meals", tags=["meals"])


@router.post(
    "/analyze",
    response_model=MealAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a food photo for AI analysis",
    description="Detects food items in the photo, estimates quantity and calories per "
    "item using OpenAI vision, and saves the result to meal history. Re-uploading the "
    "same image within the duplicate-detection window returns the existing analysis "
    "(`is_duplicate: true`) instead of calling the AI service again.",
)
async def analyze_meal(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> MealAnalyzeResponse:
    raw_bytes = await file.read()
    return meal_service.analyze_and_store_meal(
        db,
        current_user,
        storage,
        raw_bytes=raw_bytes,
        filename=file.filename or "upload.jpg",
        content_type=file.content_type,
    )


@router.post(
    "/confirm-from-menu",
    response_model=MealAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Log today's meal from the recurring office menu",
    description="Called when the user taps 'Yes' on the GET /menu/today-prompt "
    "question. Uses the office menu's stored nutrition data to create the meal "
    "record directly, without an AI vision call or photo upload. Pick the menu by "
    "day_of_week + meal_type (e.g. tuesday + lunch), or by weekly_menu_id. If the user taps "
    "'No' instead, call POST /meals/analyze with a photo as usual.",
)
def confirm_meal_from_menu(
    payload: MenuConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealAnalyzeResponse:
    return menu_service.confirm_meal_from_menu(db, current_user, payload)


@router.get("", response_model=list[MealSummaryOut], summary="List meal history")
def list_meals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    on_date: date | None = Query(
        default=None,
        alias="date",
        description="Only meals eaten on this day (YYYY-MM-DD, in your timezone)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MealSummaryOut]:
    meals = meal_service.list_meals(
        db, current_user, page=page, page_size=page_size, on_date=on_date
    )
    timezone = user_timezone(current_user)
    return [MealSummaryOut.from_model(m, timezone) for m in meals]


@router.get("/{meal_id}", response_model=MealDetailOut, summary="Get a single meal's detail")
def get_meal(
    meal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealDetailOut:
    meal = meal_service.get_meal(db, current_user, meal_id)
    return MealDetailOut.from_model(meal, user_timezone(current_user))


@router.delete(
    "/{meal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a meal",
    description="Soft-deletes the meal for audit/history purposes (marked deleted, "
    "hidden from history, but the record is kept) and removes its stored image file.",
)
def delete_meal(
    meal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> None:
    meal_service.delete_meal(db, current_user, storage, meal_id)
