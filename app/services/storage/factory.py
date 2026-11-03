from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalFilesystemStorage


@lru_cache
def get_storage(name: str) -> StorageBackend:
    """The storage called `name` ("local" or "s3"). Built once and reused, so the
    S3 client isn't recreated on every request."""
    if name == "s3":
        from app.services.storage.s3 import S3Storage  # boto3 loads only when used

        return S3Storage()
    if name == "local":
        return LocalFilesystemStorage()
    raise ValueError(f"Unknown storage backend: {name}")


def get_storage_backend() -> StorageBackend:
    """Where new uploads go (STORAGE_BACKEND). A FastAPI dependency, so tests can swap it."""
    return get_storage(settings.STORAGE_BACKEND)
