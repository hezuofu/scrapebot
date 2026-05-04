"""Kafka streaming adapter — requires aiokafka."""

from __future__ import annotations

from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage


class KafkaStorage(BaseStorage):
    def __init__(self, brokers: str = "", topic: str = "scrapebot") -> None:
        self._brokers = brokers
        self._topic = topic
        self._producer = None

    async def connect(self) -> None:
        raise NotImplementedError("KafkaStorage requires aiokafka — install with: pip install aiokafka")

    async def disconnect(self) -> None:
        pass

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        raise NotImplementedError("KafkaStorage requires aiokafka — install with: pip install aiokafka")

    async def query(self, collection: str = "default", filters: dict[str, Any] | None = None,
                    limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        raise NotImplementedError("KafkaStorage requires aiokafka — install with: pip install aiokafka")

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        raise NotImplementedError("KafkaStorage requires aiokafka — install with: pip install aiokafka")
