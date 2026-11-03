from abc import ABC, abstractmethod


class StorageBackend(ABC):
    # Saved on each meal (meals.image_storage) so its photo can be found later,
    # even after STORAGE_BACKEND changes.
    name: str

    @abstractmethod
    def save(
        self, content: bytes, filename: str, *, folder: str = "", content_type: str | None = None
    ) -> str:
        """Store the bytes under a new unique name and return its key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object at this key, if it exists."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Return the stored bytes. Raises FileNotFoundError if the key is missing."""

    def url_for(self, key: str) -> str | None:
        """A temporary link the browser can load directly, or None if this storage
        has no such link (then the API serves the bytes itself)."""
        return None
