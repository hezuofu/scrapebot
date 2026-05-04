from __future__ import annotations

import asyncio
import time


class RateLimiter:
    def __init__(self, requests_per_second: float = 1.0, burst_size: int = 5) -> None:
        self._rate = requests_per_second
        self._burst = burst_size
        self._tokens = float(burst_size)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
            await asyncio.sleep(1.0 / self._rate)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now
