from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthError, DuplicateResourceError, NotFoundError
from app.core.security import (
    create_access_token,
    generate_refresh_token_value,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.base import ensure_utc
from app.models.user import MedicalCondition, RefreshToken, User
from app.schemas.auth import TokenResponse
from app.schemas.user import SignupRequest, UserUpdateRequest
from app.services.health_metrics import compute_all_metrics
from app.services.water_goals import calculate_daily_water_goal_ml


def _normalize_condition_name(raw_name: str) -> str:
    stripped = raw_name.strip()
    # Preserve acronyms like "PCOS" as-is; title-case everything else so
    # "diabetes" and "Diabetes" dedupe to the same row.
    if stripped.isupper():
        return stripped
    return stripped.title()


def get_or_create_medical_conditions(db: Session, names: list[str]) -> list[MedicalCondition]:
    conditions = []
    for raw_name in names:
        name = _normalize_condition_name(raw_name)
        if not name:
            continue
        condition = db.execute(
            select(MedicalCondition).where(MedicalCondition.name == name)
        ).scalar_one_or_none()
        if condition is None:
            condition = MedicalCondition(name=name)
            db.add(condition)
            db.flush()
        conditions.append(condition)
    return conditions


def _apply_computed_metrics(user: User) -> None:
    metrics = compute_all_metrics(
        weight_kg=user.weight_kg,
        height_cm=user.height_cm,
        age=user.age,
        gender=user.gender,
        activity_level=user.activity_level,
    )
    user.bmi = metrics.bmi
    user.bmr = metrics.bmr
    user.tdee = metrics.tdee
    user.daily_water_goal_ml = calculate_daily_water_goal_ml(user.weight_kg, user.activity_level)


def signup(db: Session, payload: SignupRequest) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateResourceError(
            "An account with this email already exists", code="email_taken"
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        preferred_name=payload.preferred_name,
        age=payload.age,
        gender=payload.gender,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        goal=payload.goal,
        diet_preference=payload.diet_preference,
        activity_level=payload.activity_level,
        daily_budget=payload.daily_budget,
        monthly_budget=payload.monthly_budget,
        timezone=payload.timezone,
    )
    user.medical_conditions = get_or_create_medical_conditions(db, payload.medical_conditions)
    _apply_computed_metrics(user)

    db.add(user)
    db.flush()  # assigns user.id so we can self-stamp created_by/updated_by below
    user.created_by = user.id
    user.updated_by = user.id
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect email or password", code="invalid_credentials")
    if not user.is_active:
        raise AuthError("Account is disabled", code="account_disabled")
    return user


def issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token = create_access_token(user.id)

    refresh_value = generate_refresh_token_value()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_value),
        expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_token)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_value)


def rotate_refresh_token(db: Session, refresh_token_value: str) -> TokenResponse:
    token_hash = hash_refresh_token(refresh_token_value)
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if stored is None or stored.revoked_at is not None or ensure_utc(stored.expires_at) < now:
        raise AuthError("Invalid or expired refresh token", code="invalid_refresh_token")

    stored.revoked_at = now
    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise AuthError("Account is disabled", code="account_disabled")

    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


def revoke_refresh_token(db: Session, refresh_token_value: str) -> None:
    token_hash = hash_refresh_token(refresh_token_value)
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        db.commit()


_METRIC_AFFECTING_FIELDS = {"weight_kg", "height_cm", "age", "gender", "activity_level"}


def update_profile(db: Session, user: User, payload: UserUpdateRequest) -> User:
    update_data = payload.model_dump(exclude_unset=True, exclude={"medical_conditions"})
    for field, value in update_data.items():
        setattr(user, field, value)

    if payload.medical_conditions is not None:
        user.medical_conditions = get_or_create_medical_conditions(db, payload.medical_conditions)

    if _METRIC_AFFECTING_FIELDS & update_data.keys():
        _apply_computed_metrics(user)

    user.updated_by = user.id
    db.commit()
    db.refresh(user)
    return user


def soft_delete_user(db: Session, user: User) -> None:
    """Marks the account deleted for audit/history purposes instead of erasing the
    row, so "who deleted this, and when" stays answerable. Note: this leaves the
    email permanently unavailable for re-signup, and related meals/water logs/etc.
    are NOT cascade-removed (that only happens on a real DELETE) - they remain in
    the database, tied to the now-deleted account."""
    user.deleted_at = datetime.now(UTC)
    user.deleted_by = user.id
    user.is_active = False
    db.commit()


def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    return user
