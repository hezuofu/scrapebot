from __future__ import annotations

import asyncio
import random

from scrapebot.middleware.proxy.pool import ProxyPool


class ProxyRotator:
    def __init__(
        self,
        proxies: list[str] | None = None,
        rotation: str = "round_robin",
        sticky: bool = False,
    ) -> None:
        self._pool = ProxyPool(proxies)
        self._rotation = rotation
        self._sticky = sticky
        self._index = 0
        self._lock = asyncio.Lock()
        self._sticky_map: dict[str, str] = {}  # domain → proxy

    async def get_proxy(self, domain: str = "") -> str | None:
        if self._sticky and domain and domain in self._sticky_map:
            sticky = self._sticky_map[domain]
            available = await self._pool.get_available()
            if sticky in available:
                return sticky
            # sticky proxy is dead, remove mapping
            async with self._lock:
                self._sticky_map.pop(domain, None)

        available = await self._pool.get_available()
        if not available:
            return None

        if self._rotation == "random":
            proxy = random.choice(available)
        else:
            async with self._lock:
                if self._index >= len(available):
                    self._index = 0
                proxy = available[self._index]
                self._index += 1

        if self._sticky and domain:
            async with self._lock:
                self._sticky_map[domain] = proxy

        return proxy

    async def report_failure(self, proxy: str | None) -> None:
        if proxy:
            await self._pool.mark_failure(proxy)
            # Evict from sticky map
            if self._sticky:
                async with self._lock:
                    stale = [d for d, p in self._sticky_map.items() if p == proxy]
                    for d in stale:
                        del self._sticky_map[d]

    async def report_success(self, proxy: str | None) -> None:
        if proxy:
            await self._pool.mark_success(proxy)

    async def add_proxy(self, proxy: str) -> None:
        await self._pool.add(proxy)

    async def remove_proxy(self, proxy: str) -> None:
        await self._pool.remove(proxy)
