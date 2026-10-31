import uuid
from pathlib import Path

from app.core.config import settings
from app.services.storage.base import StorageBackend


class LocalFilesystemStorage(StorageBackend):
    name = "local"

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.MEDIA_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self, content: bytes, filename: str, *, folder: str = "", content_type: str | None = None
    ) -> str:
        suffix = Path(filename).suffix.lower() or ".jpg"
        key = f"{folder.strip('/')}/{uuid.uuid4().hex}{suffix}".lstrip("/")
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def delete(self, key: str) -> None:
        target = self.root / key
        if target.exists():
            target.unlink()

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()
