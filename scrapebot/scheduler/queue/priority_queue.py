from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field

from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.types import Task


@dataclass(order=True)
class _PrioritizedTask:
    priority: int
    task: Task = field(compare=False)


class PriorityQueue(AbstractQueue):
    def __init__(self) -> None:
        self._heap: list[_PrioritizedTask] = []
        self._pending: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def push(self, task: Task) -> None:
        async with self._lock:
            item = _PrioritizedTask(priority=task.priority, task=task)
            heapq.heappush(self._heap, item)

    async def pop(self) -> Task | None:
        async with self._lock:
            if not self._heap:
                return None
            item = heapq.heappop(self._heap)
            self._pending[item.task.id] = item.task
            return item.task

    async def ack(self, task_id: str) -> None:
        async with self._lock:
            self._pending.pop(task_id, None)

    async def size(self) -> int:
        return len(self._heap)

    async def peek(self) -> Task | None:
        if not self._heap:
            return None
        return self._heap[0].task

    async def remove(self, task_id: str) -> bool:
        async with self._lock:
            before = len(self._heap)
            self._heap = [t for t in self._heap if t.task.id != task_id]
            heapq.heapify(self._heap)
            return len(self._heap) < before

    async def clear(self) -> None:
        async with self._lock:
            self._heap.clear()
            self._pending.clear()
