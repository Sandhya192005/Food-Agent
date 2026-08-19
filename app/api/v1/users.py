from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdateRequest
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get the current user's profile")
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.from_model(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update the current user's profile",
    description="Partial update. If weight, height, age, gender, or activity_level "
    "change, BMI/BMR/TDEE and the daily water goal are recomputed automatically. "
    "medical_conditions, if provided, fully replaces the existing list.",
)
def update_current_user(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    updated = auth_service.update_profile(db, current_user, payload)
    return UserRead.from_model(updated)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the current user's account",
    description="Soft-deletes the account for audit/history purposes: the account is "
    "deactivated and marked deleted, but the record is kept, not erased. The email "
    "becomes permanently unavailable for a new signup.",
)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    auth_service.soft_delete_user(db, current_user)
