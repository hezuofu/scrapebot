from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from scrapebot.exceptions import CircuitBreakerOpenError


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max

        self._failures: dict[str, int] = defaultdict(int)
        self._open_until: dict[str, float] = {}
        self._half_open_count: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def check(self, host: str) -> None:
        async with self._lock:
            open_until = self._open_until.get(host, 0)
            if time.monotonic() < open_until:
                raise CircuitBreakerOpenError(f"Circuit breaker open for {host}")

    async def record_success(self, host: str) -> None:
        async with self._lock:
            self._failures[host] = 0
            self._open_until.pop(host, None)
            self._half_open_count.pop(host, None)

    async def record_failure(self, host: str) -> None:
        async with self._lock:
            self._failures[host] += 1
            if self._failures[host] >= self._failure_threshold:
                self._open_until[host] = time.monotonic() + self._recovery_timeout
