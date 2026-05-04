from __future__ import annotations

import logging
from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class MongoStorage(BaseStorage):
    def __init__(self, url: str = "", database: str = "scrapebot") -> None:
        self._url = url
        self._database = database
        self._client = None
        self._db = None

    async def connect(self) -> None:
        if not self._url:
            return
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self._client = AsyncIOMotorClient(self._url)
            self._db = self._client[self._database]
            await self._db.list_collection_names()  # verify connection
            logger.info("MongoDB connected: %s/%s", self._url.rsplit("@")[-1] if "@" in self._url else self._url, self._database)
        except ImportError:
            logger.warning("motor not installed — MongoDB storage disabled")
        except Exception as exc:
            logger.error("MongoDB connect failed: %s", exc)

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        if not self._db or not data:
            return 0
        try:
            col = self._db[collection]
            if len(data) == 1:
                result = await col.insert_one(data[0])
                return 1 if result.inserted_id else 0
            result = await col.insert_many(data)
            return len(result.inserted_ids)
        except Exception as exc:
            logger.error("MongoDB save failed: %s", exc)
            return 0

    async def query(
        self,
        collection: str = "default",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self._db:
            return []
        try:
            col = self._db[collection]
            cursor = col.find(filters or {}).skip(offset).limit(limit).sort("_id", -1)
            items = []
            async for doc in cursor:
                doc.pop("_id", None)
                items.append(doc)
            return items
        except Exception as exc:
            logger.error("MongoDB query failed: %s", exc)
            return []

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        if not self._db:
            return 0
        try:
            col = self._db[collection]
            result = await col.delete_many(filters or {})
            return result.deleted_count
        except Exception as exc:
            logger.error("MongoDB delete failed: %s", exc)
            return 0
