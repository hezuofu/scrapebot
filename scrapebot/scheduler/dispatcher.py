from __future__ import annotations

import logging

from scrapebot.config.settings import Settings
from scrapebot.types import Task, TaskResult, TaskStatus
from scrapebot.worker.executor import Executor

logger = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, settings: Settings, executor: Executor | None = None) -> None:
        self.settings = settings
        self._executor = executor or Executor(settings)

    async def dispatch(self, task: Task) -> TaskResult:
        logger.info("Dispatching task %s to %s", task.id, task.url)
        try:
            result = await self._executor.execute(task)
            logger.info("Task %s completed: %d items", task.id, len(result.data))
            return result
        except Exception as exc:
            logger.error("Task %s failed: %s", task.id, exc)
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=str(exc),
            )
