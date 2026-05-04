from __future__ import annotations

import time
import logging
from enum import Enum

from scrapebot.config.settings import Settings
from scrapebot.middleware.chain import MiddlewareAction, MiddlewareResult
from scrapebot.types import Task, TaskResult

logger = logging.getLogger(__name__)


class TriggerAction(str, Enum):
    SWITCH_PROXY = "switch_proxy"
    REDUCE_RATE = "reduce_rate"
    PAUSE = "pause"
    NOTIFY = "notify"
    SWITCH_DOWNLOADER = "switch_downloader"


class ActionTrigger:
    _RESET_AFTER = 300
    _REDUCE_FACTOR = 0.5
    _MIN_RATE = 0.1

    def __init__(self, settings: Settings, proxy_rotator=None) -> None:
        self.settings = settings
        self._proxy_rotator = proxy_rotator
        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._current_rate = settings.rate_limit.requests_per_second
        self._rate_reductions = 0

    def _maybe_reset(self) -> None:
        if time.monotonic() - self._last_failure_time > self._RESET_AFTER:
            self._consecutive_failures = 0
            self._rate_reductions = 0
            self._current_rate = self.settings.rate_limit.requests_per_second

    async def on_captcha(self, task: Task, result: TaskResult) -> MiddlewareResult | None:
        self._maybe_reset()
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        logger.warning("Captcha detected for %s (#%d)", task.url, self._consecutive_failures)

        if self._consecutive_failures >= 3:
            logger.error("Too many captcha failures — switching proxy and reducing rate")
            if self._proxy_rotator:
                current = getattr(task, "proxy", None)
                await self._proxy_rotator.report_failure(current)
            self._reduce_rate()
            return MiddlewareResult.abort(task, "Captcha block after 3 consecutive failures")

        return None

    async def on_ban(self, task: Task, result: TaskResult) -> MiddlewareResult | None:
        self._maybe_reset()
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()
        logger.warning("Ban detected for %s (#%d)", task.url, self._consecutive_failures)

        if self._proxy_rotator:
            current = getattr(task, "proxy", None)
            await self._proxy_rotator.report_failure(current)

        if self._consecutive_failures >= 5:
            logger.error("Persistent ban — task requires human review")
            return MiddlewareResult.abort(task, "Persistent ban after 5 consecutive failures")

        return None

    def _reduce_rate(self) -> None:
        self._rate_reductions += 1
        self._current_rate = max(self._MIN_RATE, self._current_rate * self._REDUCE_FACTOR)
        logger.info("Rate reduced to %.2f r/s (reduction #%d)", self._current_rate, self._rate_reductions)

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._last_failure_time = 0.0
        self._current_rate = self.settings.rate_limit.requests_per_second
        self._rate_reductions = 0
