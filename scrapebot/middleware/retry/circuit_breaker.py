from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from enum import Enum

from scrapebot.exceptions import CircuitBreakerOpenError


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 3,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max

        self._failures: dict[str, int] = defaultdict(int)
        self._open_until: dict[str, float] = {}
        self._half_open: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._states: dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)

    def state(self, host: str) -> CircuitState:
        return self._states[host]

    async def before_request(self, host: str) -> bool:
        """Returns True if the request should proceed."""
        async with self._lock:
            s = self._states[host]
            if s == CircuitState.CLOSED:
                return True
            if s == CircuitState.OPEN:
                if time.monotonic() >= self._open_until.get(host, 0):
                    self._states[host] = CircuitState.HALF_OPEN
                    self._half_open[host] = 0
                    return True
                return False
            if s == CircuitState.HALF_OPEN:
                if self._half_open[host] < self._half_open_max:
                    self._half_open[host] += 1
                    return True
                return False
        return True

    async def record_success(self, host: str) -> None:
        async with self._lock:
            self._failures[host] = 0
            if self._states[host] == CircuitState.HALF_OPEN:
                self._states[host] = CircuitState.CLOSED
                self._half_open.pop(host, None)

    async def record_failure(self, host: str) -> None:
        async with self._lock:
            self._failures[host] += 1
            if self._states[host] == CircuitState.HALF_OPEN:
                self._states[host] = CircuitState.OPEN
                self._open_until[host] = time.monotonic() + self._recovery_timeout
                self._half_open.pop(host, None)
            elif self._failures[host] >= self._failure_threshold:
                self._states[host] = CircuitState.OPEN
                self._open_until[host] = time.monotonic() + self._recovery_timeout
