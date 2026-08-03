from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.recommendation import RecommendationHistoryEntryOut, RecommendationOut
from app.services.ai import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a fresh personalized nutrition recommendation",
    description="Calls OpenAI using the user's profile, health metrics, medical "
    "conditions, diet preference, budget, recent meal history, and today's hydration "
    "progress. Not idempotent — costs an AI call and is persisted to history.",
)
def generate_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationOut:
    return recommendation_service.create_recommendation(db, current_user)


@router.get(
    "/latest",
    response_model=RecommendationOut,
    summary="Get the most recently generated recommendation",
    description="Returns the last persisted recommendation without calling OpenAI again.",
)
def latest_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationOut:
    recommendation = recommendation_service.get_latest_recommendation(db, current_user)
    if recommendation is None:
        raise NotFoundError("No recommendations yet", code="no_recommendations")
    return recommendation


@router.get(
    "/history",
    response_model=list[RecommendationHistoryEntryOut],
    summary="List past recommendations",
)
def recommendation_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendationHistoryEntryOut]:
    logs = recommendation_service.list_recommendation_history(
        db, current_user, page=page, page_size=page_size
    )
    return [RecommendationHistoryEntryOut.from_model(log) for log in logs]
