from __future__ import annotations

import asyncio
import heapq
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.scheduler.queue.priority_queue import PriorityQueue
from scrapebot.types import Task


@dataclass(order=True)
class _DelayedItem:
    fire_at: float
    task: Task = field(compare=False)


class DelayedQueue(AbstractQueue):
    def __init__(self, target_queue: AbstractQueue | None = None) -> None:
        self._heap: list[_DelayedItem] = []
        self._lock = asyncio.Lock()
        self._target = target_queue or PriorityQueue()
        self._cron_tasks: list[dict[str, Any]] = []

    async def push(self, task: Task) -> None:
        if task.scheduled_at is None:
            await self._target.push(task)
            return

        fire_at = task.scheduled_at.timestamp()
        async with self._lock:
            heapq.heappush(self._heap, _DelayedItem(fire_at=fire_at, task=task))

    async def push_delayed_retry(self, task: Task, delay_seconds: float) -> None:
        """Re-enqueue a failed task after a delay."""
        task.scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)
        await self.push(task)

    def register_cron(self, name: str, cron_expr: str, task_factory) -> None:
        """Register a cron-based recurring task.

        cron_expr: "minute hour day month weekday" (5-field standard)
        task_factory: async callable that returns a Task
        """
        self._cron_tasks.append({
            "name": name,
            "expr": cron_expr,
            "factory": task_factory,
            "last_run": None,
        })

    async def tick_cron(self) -> None:
        """Evaluate all cron tasks and enqueue those due to fire."""
        now = datetime.now()
        for ct in self._cron_tasks:
            next_time = self._next_cron(ct["expr"], ct.get("last_run"))
            if next_time and next_time <= now:
                try:
                    task = ct["factory"]()
                    if asyncio.iscoroutine(task):
                        task = await task
                    await self._target.push(task)
                    ct["last_run"] = now
                except Exception:
                    pass

    async def pop(self) -> Task | None:
        await self._drain_due()
        await self.tick_cron()
        return await self._target.pop()

    async def ack(self, task_id: str) -> None:
        await self._target.ack(task_id)

    async def size(self) -> int:
        return len(self._heap) + await self._target.size()

    async def peek(self) -> Task | None:
        await self._drain_due()
        return await self._target.peek()

    async def remove(self, task_id: str) -> bool:
        async with self._lock:
            before = len(self._heap)
            self._heap = [t for t in self._heap if t.task.id != task_id]
            heapq.heapify(self._heap)
        return len(self._heap) < before or await self._target.remove(task_id)

    async def clear(self) -> None:
        async with self._lock:
            self._heap.clear()
        await self._target.clear()

    async def _drain_due(self) -> None:
        now = datetime.now().timestamp()
        async with self._lock:
            while self._heap and self._heap[0].fire_at <= now:
                item = heapq.heappop(self._heap)
                await self._target.push(item.task)

    @staticmethod
    def _next_cron(expr: str, last_run: datetime | None) -> datetime | None:
        """Simplified cron: only handles minute-interval patterns like '*/5 * * * *'."""
        parts = expr.strip().split()
        if len(parts) != 5:
            return None
        minute_part = parts[0]
        m = re.match(r"\*/(\d+)", minute_part)
        if m:
            interval = int(m.group(1))
            base = last_run or datetime.now().replace(second=0, microsecond=0)
            return base + timedelta(minutes=interval)
        return None
