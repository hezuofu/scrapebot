from __future__ import annotations

from abc import ABC, abstractmethod

from scrapebot.types import Task


class AbstractQueue(ABC):
    @abstractmethod
    async def push(self, task: Task) -> None:
        """Push a task onto the queue."""

    @abstractmethod
    async def pop(self) -> Task | None:
        """Pop the next task from the queue. Returns None if empty."""

    @abstractmethod
    async def ack(self, task_id: str) -> None:
        """Acknowledge successful completion of a task."""

    @abstractmethod
    async def size(self) -> int:
        """Return the current queue size."""

    @abstractmethod
    async def peek(self) -> Task | None:
        """Return the next task without removing it."""

    @abstractmethod
    async def remove(self, task_id: str) -> bool:
        """Remove a specific task from the queue."""

    @abstractmethod
    async def clear(self) -> None:
        """Remove all tasks from the queue."""
