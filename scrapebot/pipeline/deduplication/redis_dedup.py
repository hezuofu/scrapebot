from __future__ import annotations

import hashlib
from typing import Any

import redis.asyncio as aioredis


class RedisDedup:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        prefix: str = "scrapebot:dedup",
        ttl: int = 86400,
    ) -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._ttl = ttl
        self._redis: aioredis.Redis | None = None

    async def _ensure_connected(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url)

    async def is_duplicate(self, item: Any) -> bool:
        await self._ensure_connected()
        key = self._make_key(item)
        added = await self._redis.set(key, "1", nx=True, ex=self._ttl)
        return not added

    async def mark_seen(self, item: Any) -> None:
        await self._ensure_connected()
        key = self._make_key(item)
        await self._redis.set(key, "1", ex=self._ttl)

    async def clear(self) -> None:
        await self._ensure_connected()
        pattern = f"{self._prefix}:*"
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

    def _make_key(self, item: Any) -> str:
        content = str(item).encode()
        digest = hashlib.sha256(content).hexdigest()[:16]
        return f"{self._prefix}:{digest}"
