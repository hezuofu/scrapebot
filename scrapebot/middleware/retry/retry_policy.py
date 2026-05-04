from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from scrapebot.types import Task, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        retry_on_status: list[int] | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.retry_on_status = retry_on_status or [429, 500, 502, 503, 504]

    async def execute(
        self,
        handler: Callable[[Task], Any],
        task: Task,
    ) -> TaskResult:
        last_result: TaskResult | None = None
        for attempt in range(1, self.max_attempts + 1):
            result = await handler(task)
            last_result = result

            if attempt >= task.max_retries + 1:
                break

            if result.status == TaskStatus.COMPLETED:
                return result

            if result.download_result and result.download_result.status_code in self.retry_on_status:
                delay = min(self.backoff_base ** attempt, self.backoff_max)
                logger.info(
                    "Retry %d/%d for %s in %.1fs (status=%d)",
                    attempt, task.max_retries, task.url, delay,
                    result.download_result.status_code,
                )
                await asyncio.sleep(delay)
                continue

            break

        return last_result
