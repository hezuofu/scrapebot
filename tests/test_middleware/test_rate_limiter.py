from __future__ import annotations

import asyncio

import pytest

from scrapebot.middleware.rate_limiter import RateLimiter
from scrapebot.types import Task


@pytest.mark.asyncio
async def test_rate_limiter_acquire():
    """High rate limit should always succeed."""
    rl = RateLimiter(requests_per_second=100, burst_size=10)
    for _ in range(5):
        ok = await rl.acquire("global")
        assert ok is True


@pytest.mark.asyncio
async def test_rate_limiter_burst_exhaustion():
    """Once burst is exhausted, acquire returns False (non-blocking)."""
    rl = RateLimiter(requests_per_second=2, burst_size=1)
    ok1 = await rl.acquire("test")
    assert ok1 is True
    ok2 = await rl.acquire("test")
    assert ok2 is False  # burst exhausted, non-blocking reject


@pytest.mark.asyncio
async def test_rate_limiter_per_domain():
    """Per-domain rate limiting isolates domains (global burst large enough)."""
    rl = RateLimiter(requests_per_second=100, burst_size=10, per_domain=True)
    ok_a = await rl.acquire(Task(url="https://example.com/page1"))
    assert ok_a is True
    ok_b = await rl.acquire(Task(url="https://other.com/page1"))
    assert ok_b is True  # different domain, should pass through both global and domain bucket


@pytest.mark.asyncio
async def test_rate_limiter_resource_group():
    """Resource group with high limit never blocks."""
    rl = RateLimiter(requests_per_second=1, burst_size=1)
    rl.add_group("vip", rate=100, burst=50)
    ok = await rl.acquire(Task(url="https://example.com"), group="vip")
    assert ok is True
