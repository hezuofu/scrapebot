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
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._retry_on_status = retry_on_status or [429, 500, 502, 503, 504]

    @property
    def max_retries(self) -> int:
        return self._max_attempts - 1

    async def execute(
        self,
        handler: Callable[[Task], Any],
        task: Task,
    ) -> TaskResult:
        last_result: TaskResult | None = None
        limit = min(self._max_attempts, task.max_retries + 1)

        for attempt in range(1, limit + 1):
            result = await handler(task)
            last_result = result

            if result.status == TaskStatus.COMPLETED:
                return result

            if attempt < limit and result.download_result:
                if result.download_result.status_code in self._retry_on_status:
                    delay = min(self._backoff_base ** attempt, self._backoff_max)
                    logger.info(
                        "Retry %d/%d for %s in %.1fs (status=%d)",
                        attempt, limit - 1, task.url, delay,
                        result.download_result.status_code,
                    )
                    await asyncio.sleep(delay)
                    continue

            break

        return last_result
