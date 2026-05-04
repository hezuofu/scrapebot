from __future__ import annotations

import asyncio
import logging

from scrapebot.config.settings import Settings
from scrapebot.events.bus import EventBus, get_event_bus
from scrapebot.events.types import Event, EventType
from scrapebot.scheduler.dispatcher import Dispatcher
from scrapebot.scheduler.load_balancer import LoadBalancer
from scrapebot.scheduler.queue.base import AbstractQueue
from scrapebot.scheduler.queue.priority_queue import PriorityQueue
from scrapebot.storage.task_store import TaskStore
from scrapebot.types import Task, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(
        self,
        settings: Settings,
        queue: AbstractQueue | None = None,
        dispatcher: Dispatcher | None = None,
        load_balancer: LoadBalancer | None = None,
        event_bus: EventBus | None = None,
        task_store: TaskStore | None = None,
    ) -> None:
        self.settings = settings
        self.queue = queue or PriorityQueue()
        self.dispatcher = dispatcher or Dispatcher(settings)
        self.load_balancer = load_balancer or LoadBalancer(settings)
        self._bus = event_bus or get_event_bus()
        self._task_store = task_store or TaskStore()
        self._running = False
        self._results: dict[str, TaskResult] = {}

    async def submit(self, task: Task) -> str:
        await self.queue.push(task)
        await self._bus.publish(Event(
            type=EventType.TASK_CREATED,
            task_id=task.id,
            message=f"Task submitted: {task.url}",
            data={"url": task.url, "mode": task.scrape_mode.value},
        ))
        logger.info("Task submitted: %s -> %s (mode=%s)", task.id, task.url, task.scrape_mode.value)
        return task.id

    async def submit_batch(self, tasks: list[Task]) -> list[str]:
        ids = []
        for task in tasks:
            ids.append(await self.submit(task))
        return ids

    async def start(self) -> None:
        self._running = True
        logger.info("Coordinator started")
        while self._running:
            task = await self.queue.pop()
            if task is None:
                await asyncio.sleep(self.settings.scheduler.poll_interval)
                continue

            result = await self.dispatcher.dispatch(task)
            self._results[task.id] = result
            await self._task_store.save(result)
            await self.queue.ack(task.id)

            if result.status == TaskStatus.FAILED:
                await self._bus.publish(Event(
                    type=EventType.TASK_FAILED,
                    task_id=task.id,
                    message=f"Task failed: {result.error}",
                    severity="error",
                ))

    async def stop(self) -> None:
        self._running = False
        logger.info("Coordinator stopped")

    def get_result(self, task_id: str) -> TaskResult | None:
        return self._results.get(task_id)

    async def get_result_async(self, task_id: str) -> TaskResult | None:
        if task_id in self._results:
            return self._results[task_id]
        return await self._task_store.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        removed = await self.queue.remove(task_id)
        if removed:
            self._results[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED,
            )
            await self._bus.publish(Event(
                type=EventType.TASK_CANCELLED,
                task_id=task_id,
                message="Task cancelled",
            ))
        return removed
