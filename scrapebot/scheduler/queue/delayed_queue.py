from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import datetime

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
        self._ready_event = asyncio.Event()
        self._target = target_queue or PriorityQueue()
        self._running = False

    async def push(self, task: Task) -> None:
        if task.scheduled_at is None:
            await self._target.push(task)
            return

        fire_at = task.scheduled_at.timestamp()
        async with self._lock:
            heapq.heappush(self._heap, _DelayedItem(fire_at=fire_at, task=task))
            self._ready_event.set()

    async def pop(self) -> Task | None:
        await self._drain_due()
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
        target_removed = await self._target.remove(task_id)
        return len(self._heap) < before or target_removed

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
