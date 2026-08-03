from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, filename: str) -> str:
        """Persist bytes under a storage-generated name, returns a relative path/key."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Remove the object at the given path/key, if it exists."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read back the raw bytes stored at the given path/key."""
