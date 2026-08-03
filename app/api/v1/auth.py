from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, SignupResponse, TokenResponse
from app.schemas.user import SignupRequest, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and profile",
    description="Creates a user with their full nutrition profile, computes BMI/BMR/TDEE "
    "and daily water goal, and returns an access/refresh token pair (auto-login).",
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    user = auth_service.signup(db, payload)
    tokens = auth_service.issue_tokens(db, user)
    return SignupResponse(user=UserRead.from_model(user), tokens=tokens)


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.authenticate(db, payload.email, payload.password)
    return auth_service.issue_tokens(db, user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair",
    description="Rotates the refresh token: the old one is revoked and a new one is issued.",
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.rotate_refresh_token(db, payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    auth_service.revoke_refresh_token(db, payload.refresh_token)
