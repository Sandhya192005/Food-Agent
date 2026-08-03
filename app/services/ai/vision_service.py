import base64
import json
import logging

import openai
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.exceptions import AIResponseInvalidError, AIServiceError, AIServiceUnavailableError
from app.services.ai.openai_client import VISION_TIMEOUT_SECONDS, get_openai_client
from app.services.ai.prompts import (
    FOOD_VISION_JSON_SCHEMA,
    FOOD_VISION_SYSTEM_PROMPT,
    FOOD_VISION_USER_PROMPT,
)
from app.services.meal_validation import RawFoodItem

logger = logging.getLogger("app.ai.vision")


class _VisionItemModel(BaseModel):
    name: str
    quantity_value: float
    quantity_unit: str
    bbox: list[float]
    approx_calories: float
    protein_g: float
    fat_g: float
    confidence: float


class _VisionResponseModel(BaseModel):
    items: list[_VisionItemModel]


def _guess_image_mime(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def analyze_food_image(image_bytes: bytes) -> list[RawFoodItem]:
    client = get_openai_client()
    mime = _guess_image_mime(image_bytes)
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_VISION_MODEL,
            timeout=VISION_TIMEOUT_SECONDS,
            messages=[
                {"role": "system", "content": FOOD_VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": FOOD_VISION_USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_schema", "json_schema": FOOD_VISION_JSON_SCHEMA},
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
            "The image could not be processed by the AI service", code="ai_bad_request"
        ) from exc
    except openai.APIError as exc:
        raise AIServiceError("AI service request failed", code="ai_api_error") from exc

    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise AIResponseInvalidError(
            "Unable to analyze image — please try a clearer photo", code="ai_refusal"
        )

    content = choice.message.content
    if not content:
        raise AIResponseInvalidError(
            "AI service returned an empty response", code="ai_empty_response"
        )

    try:
        parsed = _VisionResponseModel.model_validate(json.loads(content))
    except (json.JSONDecodeError, PydanticValidationError) as exc:
        logger.error("Failed to parse OpenAI vision response: %s", content[:500])
        raise AIResponseInvalidError(
            "AI response was invalid, please retry", code="ai_invalid_json"
        ) from exc

    items = []
    for item in parsed.items:
        bbox = item.bbox
        if len(bbox) != 4:
            continue
        bbox_tuple = tuple(max(0.0, min(v, 1.0)) for v in bbox)
        items.append(
            RawFoodItem(
                name=item.name,
                quantity_value=item.quantity_value,
                quantity_unit=item.quantity_unit,
                bbox=bbox_tuple,
                approx_calories=item.approx_calories,
                confidence=item.confidence,
                protein_g=item.protein_g,
                fat_g=item.fat_g,
            )
        )
    return items
