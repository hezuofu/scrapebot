from __future__ import annotations

from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage


class MongoStorage(BaseStorage):
    def __init__(self, url: str = "", database: str = "scrapebot") -> None:
        self._url = url
        self._database = database
        self._client = None
        self._db = None

    async def connect(self) -> None:
        if not self._url:
            return

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        return 0

    async def query(
        self,
        collection: str = "default",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return []

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        return 0
