from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any

from scrapebot.types import TaskResult, TaskStatus

logger = logging.getLogger(__name__)

_MAX_MEMORY = 10_000


class TaskStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis = None
        self._memory: OrderedDict[str, tuple[TaskResult, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _ensure_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)

    async def save(self, result: TaskResult) -> None:
        async with self._lock:
            self._memory[result.task_id] = (result, datetime.now().timestamp())
            self._evict()
        try:
            await self._ensure_redis()
            await self._redis.set(
                f"scrapebot:result:{result.task_id}",
                result.model_dump_json(),
                ex=86400,
            )
        except Exception as exc:
            logger.warning("Failed to persist task %s to Redis: %s", result.task_id, exc)

    async def get(self, task_id: str) -> TaskResult | None:
        if task_id in self._memory:
            return self._memory[task_id][0]
        try:
            await self._ensure_redis()
            raw = await self._redis.get(f"scrapebot:result:{task_id}")
            if raw:
                return TaskResult.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Failed to read task %s from Redis: %s", task_id, exc)
        return None

    async def list_pending(self) -> list[str]:
        async with self._lock:
            return [
                tid for tid, (r, _) in self._memory.items()
                if r.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    async def delete(self, task_id: str) -> None:
        async with self._lock:
            self._memory.pop(task_id, None)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    def _evict(self) -> None:
        while len(self._memory) > _MAX_MEMORY:
            self._memory.popitem(last=False)
