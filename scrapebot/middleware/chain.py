from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from scrapebot.config.settings import Settings
from scrapebot.middleware.anti_detect.action_trigger import ActionTrigger
from scrapebot.middleware.anti_detect.ban_detector import BanDetector
from scrapebot.middleware.anti_detect.captcha_detector import CaptchaDetector
from scrapebot.middleware.headers.fingerprint import BrowserFingerprint
from scrapebot.middleware.headers.ua_rotator import UARotator
from scrapebot.middleware.proxy.rotator import ProxyRotator
from scrapebot.middleware.rate_limiter import RateLimiter
from scrapebot.middleware.retry.retry_policy import RetryPolicy
from scrapebot.types import Task, TaskResult

logger = logging.getLogger(__name__)

MiddlewareFunc = Callable[[Task], Any]


class MiddlewareChain:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self._rate_limiter = RateLimiter(
            settings.rate_limit.requests_per_second,
            settings.rate_limit.burst_size,
        )
        self._ua_rotator = UARotator(settings.worker.pool_size)
        self._fingerprint = BrowserFingerprint()

        proxy_config = settings.proxy_config
        proxy_list = [s.url for pool in proxy_config.pools.values() for s in pool.servers]
        if not proxy_list:
            proxy_list = []
        self._proxy_rotator = ProxyRotator(
            proxies=proxy_list,
            rotation=proxy_config.default_pool.rotation_strategy,
        )
        self._proxy_enabled = proxy_config.enabled

        self._retry = RetryPolicy(
            max_attempts=settings.retry.max_attempts,
            backoff_base=settings.retry.backoff_base,
            backoff_max=settings.retry.backoff_max,
        )
        self._captcha_detector = CaptchaDetector()
        self._ban_detector = BanDetector()
        self._action_trigger = ActionTrigger(settings)

    def wrap(self, handler: Callable[[Task], Any]) -> Callable[[Task], Any]:
        async def wrapped(task: Task) -> TaskResult:
            await self._rate_limiter.acquire()

            enriched_headers = self._fingerprint.enrich(
                self._ua_rotator.enrich(dict(task.headers))
            )
            enriched_proxy = task.proxy
            if self._proxy_enabled and not enriched_proxy:
                enriched_proxy = await self._proxy_rotator.get_proxy()

            enriched_task = task.model_copy(update={
                "headers": enriched_headers,
                "proxy": enriched_proxy,
            })

            result = await self._retry.execute(handler, enriched_task)

            if result.download_result:
                if self._captcha_detector.detect(result.download_result.text):
                    await self._action_trigger.on_captcha(enriched_task, result)
                if self._ban_detector.detect(result.download_result):
                    await self._action_trigger.on_ban(enriched_task, result)

            return result

        return wrapped
