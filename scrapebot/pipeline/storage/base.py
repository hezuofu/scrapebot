from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStorage(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the storage backend."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the storage backend."""

    @abstractmethod
    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        """Save data items. Returns the number of items saved."""

    @abstractmethod
    async def query(
        self,
        collection: str = "default",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query data from the storage."""

    @abstractmethod
    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        """Delete matching items. Returns the number deleted."""
