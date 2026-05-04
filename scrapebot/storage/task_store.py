from __future__ import annotations

import asyncio
from typing import Any

from scrapebot.types import Task, TaskResult, TaskStatus


class TaskStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis = None
        self._memory: dict[str, TaskResult] = {}
        self._lock = asyncio.Lock()

    async def _ensure_redis(self) -> None:
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)

    async def save(self, result: TaskResult) -> None:
        async with self._lock:
            self._memory[result.task_id] = result
        try:
            await self._ensure_redis()
            await self._redis.set(
                f"scrapebot:result:{result.task_id}",
                result.model_dump_json(),
                ex=86400,
            )
        except Exception:
            pass

    async def get(self, task_id: str) -> TaskResult | None:
        if task_id in self._memory:
            return self._memory[task_id]
        try:
            await self._ensure_redis()
            raw = await self._redis.get(f"scrapebot:result:{task_id}")
            if raw:
                return TaskResult.model_validate_json(raw)
        except Exception:
            pass
        return None

    async def list_pending(self) -> list[str]:
        async with self._lock:
            return [
                tid for tid, r in self._memory.items()
                if r.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            ]

    async def delete(self, task_id: str) -> None:
        async with self._lock:
            self._memory.pop(task_id, None)
