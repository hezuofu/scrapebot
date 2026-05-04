from __future__ import annotations

import asyncio
import random

from scrapebot.middleware.proxy.pool import ProxyPool


class ProxyRotator:
    def __init__(
        self,
        proxies: list[str] | None = None,
        rotation: str = "round_robin",
    ) -> None:
        self._pool = ProxyPool(proxies)
        self._rotation = rotation
        self._index = 0
        self._lock = asyncio.Lock()

    async def get_proxy(self) -> str | None:
        available = await self._pool.get_available()
        if not available:
            return None

        if self._rotation == "random":
            return random.choice(available)

        async with self._lock:
            if self._index >= len(available):
                self._index = 0
            proxy = available[self._index]
            self._index += 1
            return proxy

    async def report_failure(self, proxy: str | None) -> None:
        if proxy:
            await self._pool.mark_failure(proxy)

    async def report_success(self, proxy: str | None) -> None:
        if proxy:
            await self._pool.mark_success(proxy)

    def add_proxy(self, proxy: str) -> None:
        self._pool.add(proxy)

    def remove_proxy(self, proxy: str) -> None:
        self._pool.remove(proxy)
