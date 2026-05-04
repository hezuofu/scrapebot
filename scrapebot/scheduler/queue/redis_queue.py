from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.types import Task


class RedisQueue(AbstractQueue):
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key: str = "scrapebot:queue",
    ) -> None:
        self._redis_url = redis_url
        self._key = key
        self._processing_key = f"{key}:processing"
        self._redis: aioredis.Redis | None = None

    async def _ensure_connected(self) -> None:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url)

    async def push(self, task: Task) -> None:
        await self._ensure_connected()
        score = task.priority if task.scheduled_at is None else task.scheduled_at.timestamp()
        await self._redis.zadd(self._key, {task.model_dump_json(): score})

    async def pop(self) -> Task | None:
        await self._ensure_connected()
        # Atomic: move from queue to processing, then parse
        raw = await self._redis.eval(
            """
            local items = redis.call('ZRANGE', KEYS[1], 0, 0)
            if #items == 0 then return nil end
            redis.call('ZREM', KEYS[1], items[1])
            redis.call('SADD', KEYS[2], items[1])
            return items[1]
            """,
            2, self._key, self._processing_key,
        )
        if raw is None:
            return None
        return Task.model_validate_json(raw)

    async def ack(self, task_id: str) -> None:
        await self._ensure_connected()
        # Remove from processing set — find by task_id
        members = await self._redis.smembers(self._processing_key)
        for raw in members:
            try:
                if f'"id":"{task_id}"' in raw:
                    await self._redis.srem(self._processing_key, raw)
                    break
            except Exception:
                continue

    async def recover(self) -> list[Task]:
        """Recover un-acked tasks from processing set (e.g. after crash)."""
        await self._ensure_connected()
        members = await self._redis.smembers(self._processing_key)
        tasks = []
        for raw in members:
            try:
                task = Task.model_validate_json(raw)
                tasks.append(task)
                await self._redis.srem(self._processing_key, raw)
            except Exception:
                continue
        return tasks

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
            if f'"id":"{task_id}"' in raw:
                await self._redis.zrem(self._key, raw)
                return True
        return False

    async def clear(self) -> None:
        await self._ensure_connected()
        await self._redis.delete(self._key, self._processing_key)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
