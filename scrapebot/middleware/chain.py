from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from scrapebot.types import Task, TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class MiddlewareAction(str, Enum):
    CONTINUE = "continue"
    ABORT = "abort"


class MiddlewareResult:
    __slots__ = ("action", "task", "message")

    def __init__(self, action: MiddlewareAction, task: Task, message: str = "") -> None:
        self.action = action
        self.task = task
        self.message = message

    @classmethod
    def ok(cls, task: Task) -> MiddlewareResult:
        return cls(MiddlewareAction.CONTINUE, task)

    @classmethod
    def abort(cls, task: Task, reason: str) -> MiddlewareResult:
        return cls(MiddlewareAction.ABORT, task, reason)


class MiddlewareChain:
    def __init__(
        self,
        rate_limiter: Any = None,
        enrichers: list[Any] | None = None,
        retry_policy: Any = None,
        post_processors: list[Any] | None = None,
        proxy_enabled: bool = False,
        proxy_rotator: Any = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._enrichers = enrichers or []
        self._retry = retry_policy
        self._post_processors = post_processors or []
        self._proxy_enabled = proxy_enabled
        self._proxy_rotator = proxy_rotator

    def wrap(self, handler: Callable[[Task], Any]) -> Callable[[Task], Any]:
        async def wrapped(task: Task) -> TaskResult:
            # ---- rate limit (interruptible) ----
            if self._rate_limiter:
                ok = await self._rate_limiter.acquire(task)
                if not ok:
                    return TaskResult(task_id=task.id, status=TaskStatus.FAILED,
                                      error="Rate limit exceeded")

            # ---- enrich (immutable) ----
            enriched_headers = dict(task.headers)
            for enricher in self._enrichers:
                enriched_headers = enricher.enrich(enriched_headers)

            enriched_proxy = task.proxy
            if self._proxy_enabled and not enriched_proxy and self._proxy_rotator:
                domain = self._domain_for(task.url)
                enriched_proxy = await self._proxy_rotator.get_proxy(domain=domain)

            enriched_task = task.model_copy(update={
                "headers": enriched_headers,
                "proxy": enriched_proxy,
            })

            # ---- execute ----
            if self._retry:
                result = await self._retry.execute(handler, enriched_task)
            else:
                result = await handler(enriched_task)

            # ---- post-process (interruptible) ----
            for proc in self._post_processors:
                mr = await self._invoke_post(proc, enriched_task, result)
                if mr and mr.action == MiddlewareAction.ABORT:
                    return TaskResult(task_id=task.id, status=TaskStatus.FAILED,
                                      error=f"Aborted: {mr.message}")

            return result

        return wrapped

    async def _invoke_post(self, proc: Any, task: Task, result: TaskResult) -> MiddlewareResult | None:
        if result.download_result is None:
            return None
        try:
            dl = result.download_result
            from scrapebot.middleware.anti_detect.captcha_detector import CaptchaDetector
            from scrapebot.middleware.anti_detect.ban_detector import BanDetector
            from scrapebot.middleware.anti_detect.action_trigger import ActionTrigger

            if isinstance(proc, CaptchaDetector):
                if proc.detect(dl.text) and proc._trigger:
                    return await proc._trigger.on_captcha(task, result)
            elif isinstance(proc, BanDetector):
                if proc.detect(dl) and proc._trigger:
                    return await proc._trigger.on_ban(task, result)
            elif isinstance(proc, ActionTrigger):
                pass
            elif hasattr(proc, "on_captcha"):
                return await proc.on_captcha(task, result)
            elif hasattr(proc, "on_ban"):
                return await proc.on_ban(task, result)
        except Exception:
            logger.exception("Post-processor %s failed", proc)
        return None

    @staticmethod
    def _domain_for(url: str) -> str:
        try:
            return urlparse(url).netloc
        except Exception:
            return url
