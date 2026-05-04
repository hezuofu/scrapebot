from __future__ import annotations

from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage


class KafkaStorage(BaseStorage):
    def __init__(self, brokers: str = "", topic: str = "scrapebot") -> None:
        self._brokers = brokers
        self._topic = topic
        self._producer = None

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

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
