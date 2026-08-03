from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_VISION_MODEL: str = "gpt-4.1"
    OPENAI_TEXT_MODEL: str = "gpt-4.1-mini"

    # Database
    DATABASE_URL: str = "sqlite:///./data/food_agent.db"

    # Storage
    MEDIA_ROOT: str = "./media"

    # Tokens
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Water tracking
    WATER_REMINDER_THRESHOLD_MINUTES: int = 90
    WATER_SNOOZE_MINUTES: int = 60

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 10
    # Comma-separated string, not a list: pydantic-settings tries to JSON-decode
    # list-typed fields from env vars, which breaks plain comma-separated values.
    # Exposed as a parsed list via the `allowed_image_types` property below.
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"
    DUPLICATE_UPLOAD_WINDOW_MINUTES: int = 15

    # Meal analysis bounds
    MAX_ITEM_CALORIES: float = 1200
    MAX_MEAL_CALORIES: float = 4000
    LOW_CONFIDENCE_THRESHOLD: float = 0.5

    # Misc
    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"
    CORS_ORIGINS: str = ""
    LOG_LEVEL: str = "INFO"

    @staticmethod
    def _split(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def allowed_image_types(self) -> list[str]:
        return self._split(self.ALLOWED_IMAGE_TYPES)

    @property
    def cors_origins(self) -> list[str]:
        return self._split(self.CORS_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
