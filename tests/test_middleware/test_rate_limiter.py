from __future__ import annotations

import time
import asyncio

import pytest

from scrapebot.middleware.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_acquire():
    rl = RateLimiter(requests_per_second=100, burst_size=10)
    # Should not block at all with high rate
    await asyncio.wait_for(rl.acquire(), timeout=1.0)


@pytest.mark.asyncio
async def test_rate_limiter_burst_exhaustion():
    rl = RateLimiter(requests_per_second=2, burst_size=1)
    await rl.acquire()
    # Next acquire should need to wait ~0.5s
    start = time.monotonic()
    await asyncio.wait_for(rl.acquire(), timeout=2.0)
    elapsed = time.monotonic() - start
    assert elapsed > 0.2
