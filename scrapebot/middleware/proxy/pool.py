from __future__ import annotations

import asyncio
import time


class ProxyPool:
    def __init__(self, proxies: list[str] | None = None, cooldown_seconds: float = 60.0) -> None:
        self._proxies: dict[str, dict] = {}
        self._cooldown = cooldown_seconds
        self._lock = asyncio.Lock()
        for proxy in (proxies or []):
            self._proxies[proxy] = {"failures": 0, "cooldown_until": 0}

    def add(self, proxy: str) -> None:
        self._proxies[proxy] = {"failures": 0, "cooldown_until": 0}

    def remove(self, proxy: str) -> None:
        self._proxies.pop(proxy, None)

    async def mark_failure(self, proxy: str) -> None:
        async with self._lock:
            if proxy in self._proxies:
                self._proxies[proxy]["failures"] += 1
                self._proxies[proxy]["cooldown_until"] = time.monotonic() + self._cooldown

    async def mark_success(self, proxy: str) -> None:
        async with self._lock:
            if proxy in self._proxies:
                self._proxies[proxy]["failures"] = 0

    async def get_available(self) -> list[str]:
        now = time.monotonic()
        async with self._lock:
            return [
                p for p, info in self._proxies.items()
                if info["cooldown_until"] <= now
            ]

    async def get_active_count(self) -> int:
        available = await self.get_available()
        return len(available)
