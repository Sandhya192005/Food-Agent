from fastapi import APIRouter, Depends, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.meal import MealAnalyzeResponse, MealDetailOut, MealSummaryOut
from app.services import meal_service
from app.services.storage.base import StorageBackend
from app.services.storage.local import get_storage_backend

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


@router.get("", response_model=list[MealSummaryOut], summary="List meal history")
def list_meals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MealSummaryOut]:
    meals = meal_service.list_meals(db, current_user, page=page, page_size=page_size)
    return [MealSummaryOut.from_model(m) for m in meals]


@router.get("/{meal_id}", response_model=MealDetailOut, summary="Get a single meal's detail")
def get_meal(
    meal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MealDetailOut:
    meal = meal_service.get_meal(db, current_user, meal_id)
    return MealDetailOut.from_model(meal)


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
