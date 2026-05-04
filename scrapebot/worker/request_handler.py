from __future__ import annotations

import logging
from typing import Any

from scrapebot.config.settings import Settings
from scrapebot.middleware.chain import MiddlewareChain
from scrapebot.types import Task, TaskResult
from scrapebot.worker.executor import Executor

logger = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self, settings: Settings, executor: Executor | None = None) -> None:
        self.settings = settings
        self._executor = executor or Executor(settings)
        self._middleware = MiddlewareChain(settings)

    async def handle(self, task: Task) -> TaskResult:
        logger.info("Handling request: %s %s", task.method, task.url)
        return await self._middleware.wrap(self._executor.execute)(task)

    async def submit(self, task: Task) -> TaskResult:
        return await self.handle(task)
