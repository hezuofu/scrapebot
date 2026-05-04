from __future__ import annotations

import logging

from scrapebot.config.settings import Settings
from scrapebot.types import Task, TaskResult

logger = logging.getLogger(__name__)


class ActionTrigger:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._consecutive_failures = 0

    async def on_captcha(self, task: Task, result: TaskResult) -> None:
        logger.warning("Captcha detected for %s", task.url)
        self._consecutive_failures += 1
        if self._consecutive_failures >= 3:
            logger.error("Multiple captcha failures, consider reducing rate or switching IPs")

    async def on_ban(self, task: Task, result: TaskResult) -> None:
        self._consecutive_failures += 1
        logger.warning(
            "Ban/rate-limit detected for %s (consecutive=%d)",
            task.url,
            self._consecutive_failures,
        )

    def reset(self) -> None:
        self._consecutive_failures = 0
