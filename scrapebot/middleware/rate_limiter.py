from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse

from scrapebot.types import Task


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float = 1.0,
        burst_size: int = 5,
        per_domain: bool = True,
    ) -> None:
        self._rate = requests_per_second
        self._burst = burst_size
        self._per_domain = per_domain
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(requests_per_second, burst_size))
        self._global = _TokenBucket(requests_per_second, burst_size)
        self._groups: dict[str, _TokenBucket] = {}

    def add_group(self, name: str, rate: float, burst: int) -> None:
        self._groups[name] = _TokenBucket(rate, burst)

    async def acquire(self, task_or_key: Task | str = "global", group: str = "") -> bool:
        key = task_or_key if isinstance(task_or_key, str) else self._key_for(task_or_key)
        if group and group in self._groups:
            return await self._groups[group].acquire()

        ok = await self._global.acquire()
        if self._per_domain and key != "global":
            ok = ok and await self._buckets[key].acquire()
        return ok

    def _key_for(self, task: Task) -> str:
        try:
            return urlparse(task.url).netloc
        except Exception:
            return task.url

    def current_rate(self, task: Task) -> float:
        key = self._key_for(task)
        return self._buckets[key].current_rate()


class _TokenBucket:
    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(float(self._burst), self._tokens + elapsed * self._rate)
        self._last_refill = now

    def current_rate(self) -> float:
        return self._rate
