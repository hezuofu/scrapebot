from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

from scrapebot.config.settings import Settings
from scrapebot.scheduler.load_balancer import LoadBalancer
from scrapebot.types import Task, TaskResult, TaskStatus
from scrapebot.worker.executor import Executor

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(
        self,
        settings: Settings,
        executor: Executor | None = None,
        load_balancer: LoadBalancer | None = None,
    ) -> None:
        self.settings = settings
        self._executor = executor or Executor(settings, event_bus=None)
        self._lb = load_balancer or LoadBalancer(settings)
        self._affinity: dict[str, str] = {}  # domain → worker_id
        self._lock = asyncio.Lock()

    async def dispatch(self, task: Task) -> TaskResult:
        domain = self._domain_for(task.url)

        worker = await self._lb.select_worker()
        if worker:
            logger.info("Dispatching %s → worker %s (%s)", task.id, worker.id, domain)
        else:
            logger.info("Dispatching %s locally (%s)", task.id, domain)

        try:
            result = await self._executor.execute(task)
            return result
        except Exception as exc:
            logger.error("Task %s failed: %s", task.id, exc)
            return TaskResult(task_id=task.id, status=TaskStatus.FAILED, error=str(exc))

    async def dispatch_affinity(self, task: Task) -> TaskResult:
        """Dispatch to a worker with affinity for this domain."""
        domain = self._domain_for(task.url)
        async with self._lock:
            worker_id = self._affinity.get(domain)

        if worker_id:
            workers = await self._lb.get_workers()
            matched = [w for w in workers if w.id == worker_id and w.status == "idle"]
            if matched:
                worker = matched[0]
                logger.debug("Affinity: %s → worker %s (%s)", task.id, worker_id, domain)
                # In a real distributed system, send to that worker
                # For local mode: execute directly
                return await self._executor.execute(task)

        # No affinity yet, pick best worker
        worker = await self._lb.select_worker()
        if worker:
            async with self._lock:
                self._affinity[domain] = worker.id

        return await self._executor.execute(task)

    async def dispatch_batch(self, tasks: list[Task]) -> list[TaskResult]:
        """Dispatch tasks in parallel across available workers."""
        async def run_one(task: Task) -> TaskResult:
            return await self.dispatch(task)
        return list(await asyncio.gather(*(run_one(t) for t in tasks)))

    @staticmethod
    def _domain_for(url: str) -> str:
        try:
            return urlparse(url).netloc or url
        except Exception:
            return url
