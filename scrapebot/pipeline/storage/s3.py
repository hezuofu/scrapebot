"""S3/OSS storage adapter — requires boto3."""

from __future__ import annotations

from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage


class S3Storage(BaseStorage):
    def __init__(self, endpoint: str = "", bucket: str = "", prefix: str = "scrapebot/") -> None:
        self._endpoint = endpoint
        self._bucket = bucket
        self._prefix = prefix
        self._client = None

    async def connect(self) -> None:
        raise NotImplementedError("S3Storage requires boto3 — install with: pip install boto3")

    async def disconnect(self) -> None:
        pass

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        raise NotImplementedError("S3Storage requires boto3 — install with: pip install boto3")

    async def query(self, collection: str = "default", filters: dict[str, Any] | None = None,
                    limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        raise NotImplementedError("S3Storage requires boto3 — install with: pip install boto3")

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        raise NotImplementedError("S3Storage requires boto3 — install with: pip install boto3")
