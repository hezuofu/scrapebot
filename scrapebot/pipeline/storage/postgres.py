from __future__ import annotations

from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage


class PostgresStorage(BaseStorage):
    def __init__(self, dsn: str = "") -> None:
        self._dsn = dsn
        self._pool = None

    async def connect(self) -> None:
        if not self._dsn:
            return

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()

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
