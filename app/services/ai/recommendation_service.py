import json
import logging

import openai
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.constants import DEFAULT_CURRENCY
from app.core.exceptions import AIResponseInvalidError, AIServiceError, AIServiceUnavailableError
from app.models.meal import Meal
from app.models.recommendation import RecommendationLog
from app.models.user import User
from app.schemas.recommendation import RecommendationOut
from app.services.ai.openai_client import TEXT_TIMEOUT_SECONDS, get_openai_client
from app.services.ai.prompts import (
    NUTRITION_RECOMMENDATION_JSON_SCHEMA,
    NUTRITION_RECOMMENDATION_SYSTEM_PROMPT,
)
from app.services.water_service import get_today_summary

logger = logging.getLogger("app.ai.recommendation")

RECENT_MEAL_LIMIT = 10


def build_context(db: Session, user: User) -> dict:
    recent_meals = list(
        db.execute(
            select(Meal)
            .options(selectinload(Meal.items))
            .where(Meal.user_id == user.id)
            .order_by(Meal.captured_at.desc())
            .limit(RECENT_MEAL_LIMIT)
        ).scalars()
    )
    water_today = get_today_summary(db, user)

    return {
        "profile": {
            "preferred_name": user.preferred_name,
            "age": user.age,
            "gender": user.gender.value,
            "height_cm": user.height_cm,
            "weight_kg": user.weight_kg,
            "goal": user.goal.value,
            "diet_preference": user.diet_preference.value,
            "activity_level": user.activity_level.value,
            "medical_conditions": sorted(mc.name for mc in user.medical_conditions),
            "daily_budget": user.daily_budget,
            "monthly_budget": user.monthly_budget,
            "currency": DEFAULT_CURRENCY,
        },
        "metrics": {
            "bmi": user.bmi,
            "bmr": user.bmr,
            "tdee": user.tdee,
            "daily_water_goal_ml": user.daily_water_goal_ml,
        },
        "recent_meals": [
            {
                "captured_at": meal.captured_at.isoformat(),
                "total_calories": meal.total_calories,
                "items": [item.name for item in meal.items],
            }
            for meal in recent_meals
        ],
        "water_today": water_today.model_dump(),
    }


def generate_recommendation(context: dict) -> tuple[RecommendationOut, str]:
    client = get_openai_client()
    model = settings.OPENAI_TEXT_MODEL

    try:
        response = client.chat.completions.create(
            model=model,
            timeout=TEXT_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": NUTRITION_RECOMMENDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "### USER CONTEXT (JSON) ###\n"
                    + json.dumps(context, indent=2, default=str),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": NUTRITION_RECOMMENDATION_JSON_SCHEMA,
            },
        )
    except openai.AuthenticationError as exc:
        logger.error("OpenAI authentication failed: %s", exc)
        raise AIServiceError(
            "AI service is misconfigured", code="ai_service_config_error", status_code=500
        ) from exc
    except openai.RateLimitError as exc:
        raise AIServiceUnavailableError(
            "AI service is busy, please try again shortly", code="ai_rate_limited"
        ) from exc
    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        raise AIServiceUnavailableError(
            "AI service timed out, please try again", code="ai_timeout"
        ) from exc
    except openai.BadRequestError as exc:
        raise AIResponseInvalidError(
            "The request could not be processed by the AI service", code="ai_bad_request"
        ) from exc
    except openai.APIError as exc:
        raise AIServiceError("AI service request failed", code="ai_api_error") from exc

    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise AIResponseInvalidError(
            "Unable to generate a recommendation right now, please try again",
            code="ai_refusal",
        )

    content = choice.message.content
    if not content:
        raise AIResponseInvalidError(
            "AI service returned an empty response", code="ai_empty_response"
        )

    try:
        recommendation = RecommendationOut.model_validate(json.loads(content))
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        logger.error("Failed to parse OpenAI recommendation response: %s", content[:500])
        raise AIResponseInvalidError(
            "AI response was invalid, please retry", code="ai_invalid_json"
        ) from exc

    return recommendation, model


def create_recommendation(db: Session, user: User) -> RecommendationOut:
    context = build_context(db, user)
    recommendation, model_used = generate_recommendation(context)

    log = RecommendationLog(
        user_id=user.id,
        request_context_snapshot=json.dumps(context, default=str),
        response_json=recommendation.model_dump_json(),
        model_used=model_used,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(log)
    db.commit()

    return recommendation


def get_latest_recommendation(db: Session, user: User) -> RecommendationOut | None:
    log = db.execute(
        select(RecommendationLog)
        .where(RecommendationLog.user_id == user.id)
        .order_by(RecommendationLog.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if log is None:
        return None
    return RecommendationOut.model_validate(json.loads(log.response_json))


def list_recommendation_history(
    db: Session, user: User, *, page: int, page_size: int
) -> list[RecommendationLog]:
    offset = (page - 1) * page_size
    return list(
        db.execute(
            select(RecommendationLog)
            .where(RecommendationLog.user_id == user.id)
            .order_by(RecommendationLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).scalars()
    )
