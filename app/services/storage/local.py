import uuid
from pathlib import Path

from app.core.config import settings
from app.services.storage.base import StorageBackend


class LocalFilesystemStorage(StorageBackend):
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".jpg"
        key = f"{uuid.uuid4().hex}{suffix}"
        (self.root / key).write_bytes(content)
        return key

    def delete(self, path: str) -> None:
        target = self.root / path
        if target.exists():
            target.unlink()

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()


def get_storage_backend() -> StorageBackend:
    return LocalFilesystemStorage()
