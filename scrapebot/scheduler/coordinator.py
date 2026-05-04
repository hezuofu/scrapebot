from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict, defaultdict
from datetime import datetime
from urllib.parse import urlparse

from scrapebot.config.settings import Settings
from scrapebot.events.bus import EventBus
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
        if event_bus is None:
            raise ValueError("Coordinator requires an EventBus instance")
        self._bus = event_bus
        self._task_store = task_store or TaskStore()
        self._running = False
        self._stop_event = asyncio.Event()
        self._completion_events: dict[str, asyncio.Event] = {}
        self._results: OrderedDict[str, tuple[TaskResult, float]] = OrderedDict()
        # dependency tracking
        self._dependencies: dict[str, list[str]] = defaultdict(list)
        self._dependents: dict[str, list[str]] = defaultdict(list)
        self._paused: set[str] = set()
        self._in_flight: set[str] = set()

    # ── submit ───────────────────────────────────────────────

    async def submit(self, task: Task, depends_on: list[str] | None = None) -> str:
        if depends_on:
            pending_deps = [d for d in depends_on if d not in self._results]
            if pending_deps:
                self._dependencies[task.id] = pending_deps
                for dep in pending_deps:
                    self._dependents[dep].append(task.id)
                task.metadata["depends_on"] = pending_deps
                logger.info("Task %s waiting on dependencies: %s", task.id, pending_deps)
                await self._task_store.save(TaskResult(task_id=task.id, status=TaskStatus.PENDING))

        if not depends_on or not self._dependencies.get(task.id):
            await self._enqueue(task)

        await self._bus.publish(Event(type=EventType.TASK_CREATED, task_id=task.id,
            message=f"Task submitted: {task.url}"))
        return task.id

    async def _enqueue(self, task: Task) -> None:
        await self.queue.push(task)
        self._completion_events[task.id] = asyncio.Event()

    async def submit_batch(self, tasks: list[Task]) -> list[str]:
        return list(await asyncio.gather(*(self.submit(t) for t in tasks)))

    # ── lifecycle ────────────────────────────────────────────

    async def wait_for(self, task_id: str, timeout: float = 60.0) -> TaskResult | None:
        event = self._completion_events.get(task_id)
        if event is None:
            return self.get_result(task_id)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        return self.get_result(task_id)

    async def pause(self, task_id: str) -> bool:
        if task_id in self._in_flight:
            logger.warning("Cannot pause in-flight task %s", task_id)
            return False
        removed = await self.queue.remove(task_id)
        if removed:
            self._paused.add(task_id)
            await self._bus.publish(Event(type=EventType.TASK_CANCELLED, task_id=task_id,
                message="Task paused"))
            logger.info("Task %s paused", task_id)
            return True
        return False

    async def resume(self, task_id: str) -> bool:
        if task_id not in self._paused:
            return False
        self._paused.discard(task_id)
        entry = self._results.get(task_id)
        result = entry[0] if entry else None
        if result:
            task = Task(url="", metadata={"resumed_from": task_id})
            await self._enqueue(task)
        await self._bus.publish(Event(type=EventType.TASK_CREATED, task_id=task_id,
            message="Task resumed"))
        logger.info("Task %s resumed", task_id)
        return True

    async def cancel(self, task_id: str) -> bool:
        removed = await self.queue.remove(task_id)
        self._paused.discard(task_id)
        if removed:
            self._add_result(task_id, TaskResult(task_id=task_id, status=TaskStatus.CANCELLED))
            self._complete(task_id)
            await self._bus.publish(Event(type=EventType.TASK_CANCELLED, task_id=task_id,
                message="Task cancelled"))
        return removed

    # ── main loop ────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        logger.info("Coordinator started")
        while self._running:
            task = await self.queue.pop()
            if task is None:
                try:
                    await asyncio.wait_for(self._stop_event.wait(),
                                           timeout=self.settings.scheduler.poll_interval)
                except asyncio.TimeoutError:
                    continue
                if self._stop_event.is_set():
                    break
                continue

            self._in_flight.add(task.id)
            try:
                result = await asyncio.wait_for(
                    self.dispatcher.dispatch(task),
                    timeout=self.settings.scheduler.task_timeout,
                )
            except asyncio.TimeoutError:
                result = TaskResult(task_id=task.id, status=TaskStatus.FAILED,
                    error=f"Task timed out after {self.settings.scheduler.task_timeout}s")
                await self._bus.publish(Event(type=EventType.TASK_FAILED, task_id=task.id,
                    message=result.error, severity="error"))
            finally:
                self._in_flight.discard(task.id)

            self._add_result(task.id, result)
            await self._task_store.save(result)
            await self.queue.ack(task.id)
            self._complete(task.id)

            if result.status == TaskStatus.FAILED:
                await self._bus.publish(Event(type=EventType.TASK_FAILED, task_id=task.id,
                    message=f"Task failed: {result.error}", severity="error"))
            else:
                await self._bus.publish(Event(type=EventType.TASK_COMPLETED, task_id=task.id,
                    message=f"Task completed: {len(result.data)} items"))

            # Unblock dependent tasks
            deps = self._dependents.pop(task.id, [])
            for dep_id in deps:
                dep_deps = self._dependencies.get(dep_id, [])
                if task.id in dep_deps:
                    dep_deps.remove(task.id)
                if not dep_deps:
                    self._dependencies.pop(dep_id, None)

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        logger.info("Coordinator stopped")

    # ── query ────────────────────────────────────────────────

    def get_result(self, task_id: str) -> TaskResult | None:
        entry = self._results.get(task_id)
        return entry[0] if entry else None

    async def get_result_async(self, task_id: str) -> TaskResult | None:
        if task_id in self._results:
            return self._results[task_id][0]
        return await self._task_store.get(task_id)

    def is_paused(self, task_id: str) -> bool:
        return task_id in self._paused

    # ── internal ─────────────────────────────────────────────

    def _complete(self, task_id: str) -> None:
        event = self._completion_events.pop(task_id, None)
        if event:
            event.set()

    def _add_result(self, task_id: str, result: TaskResult) -> None:
        self._results[task_id] = (result, datetime.now().timestamp())
        max_entries = getattr(self.settings.task, "task_queue_max_size", 10_000)
        while len(self._results) > max_entries:
            self._results.popitem(last=False)
        now = datetime.now().timestamp()
        ttl = getattr(self.settings.task, "result_ttl_seconds", 3600)
        expired = [k for k, (_, ts) in self._results.items() if now - ts > ttl]
        for k in expired:
            del self._results[k]
