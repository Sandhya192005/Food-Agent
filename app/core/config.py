from functools import lru_cache
from typing import Literal

from pydantic import model_validator
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

    # Storage: where new meal photos are saved. "local" = MEDIA_ROOT folder,
    # "s3" = an AWS S3 bucket. Each meal remembers where its photo went, so
    # switching only affects new uploads.
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    MEDIA_ROOT: str = "./media"

    # AWS S3 (only used when STORAGE_BACKEND=s3)
    S3_BUCKET_NAME: str = ""
    AWS_REGION: str = "ap-south-1"
    # Leave empty to use boto3's normal lookup (~/.aws/credentials, IAM role, ...).
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    # How long a photo link from GET /meals/{id} keeps working.
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 900

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

    @model_validator(mode="after")
    def _check_s3(self) -> "Settings":
        if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME must be set when STORAGE_BACKEND=s3")
        return self

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
