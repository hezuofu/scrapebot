from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.types import Task


class RedisQueue(AbstractQueue):
    def __init__(self, redis_url: str = "redis://localhost:6379/0", key: str = "scrapebot:queue") -> None:
        self._redis_url = redis_url
        self._key = key
        self._pending_key = f"{key}:pending"
        self._redis: aioredis.Redis | None = None

    async def _ensure_connected(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url)

    async def push(self, task: Task) -> None:
        await self._ensure_connected()
        data = task.model_dump_json()
        score = task.priority if task.scheduled_at is None else task.scheduled_at.timestamp()
        await self._redis.zadd(self._key, {data: score})

    async def pop(self) -> Task | None:
        await self._ensure_connected()
        results = await self._redis.zpopmin(self._key, count=1)
        if not results:
            return None
        raw = results[0][0]
        task = Task.model_validate_json(raw)
        await self._redis.sadd(self._pending_key, task.id)
        return task

    async def ack(self, task_id: str) -> None:
        await self._ensure_connected()
        await self._redis.srem(self._pending_key, task_id)

    async def size(self) -> int:
        await self._ensure_connected()
        return await self._redis.zcard(self._key)

    async def peek(self) -> Task | None:
        await self._ensure_connected()
        results = await self._redis.zrange(self._key, 0, 0)
        if not results:
            return None
        return Task.model_validate_json(results[0])

    async def remove(self, task_id: str) -> bool:
        await self._ensure_connected()
        results = await self._redis.zrange(self._key, 0, -1)
        for raw in results:
            try:
                data = json.loads(raw)
                if data.get("id") == task_id:
                    await self._redis.zrem(self._key, raw)
                    return True
            except json.JSONDecodeError:
                continue
        return False

    async def clear(self) -> None:
        await self._ensure_connected()
        await self._redis.delete(self._key, self._pending_key)
