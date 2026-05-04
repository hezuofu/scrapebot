from __future__ import annotations

import asyncio
import heapq
import time
from dataclasses import dataclass, field

from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.types import Task


class PriorityLevel:
    CRITICAL = -20
    HIGH = -10
    NORMAL = 0
    LOW = 10
    BATCH = 20


@dataclass(order=True)
class _AgedTask:
    effective_priority: float
    task: Task = field(compare=False)
    enqueued_at: float = field(default_factory=time.monotonic, compare=False)


class PriorityQueue(AbstractQueue):
    def __init__(self, aging_factor: float = 0.1) -> None:
        self._heap: list[_AgedTask] = []
        self._pending: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._aging_factor = aging_factor

    async def push(self, task: Task) -> None:
        async with self._lock:
            item = _AgedTask(effective_priority=float(task.priority), task=task)
            heapq.heappush(self._heap, item)

    async def pop(self) -> Task | None:
        async with self._lock:
            self._age_tasks()
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
        async with self._lock:
            self._age_tasks()
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

    def _age_tasks(self) -> None:
        """Boost priority of long-waiting tasks to prevent starvation."""
        now = time.monotonic()
        aged: list[_AgedTask] = []
        for item in self._heap:
            wait_time = now - item.enqueued_at
            boost = wait_time * self._aging_factor
            item.effective_priority = float(item.task.priority) - boost
            aged.append(item)
        # Re-heapify with updated priorities
        heapq.heapify(aged)
        self._heap = aged
