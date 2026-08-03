from functools import lru_cache

from openai import OpenAI

from app.core.config import settings

VISION_TIMEOUT_SECONDS = 30
TEXT_TIMEOUT_SECONDS = 20
MAX_RETRIES = 2


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=MAX_RETRIES)
