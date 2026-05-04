from __future__ import annotations

import asyncio
from typing import Any


class ResultStore:
    def __init__(self) -> None:
        self._results: dict[str, list[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def save(self, task_id: str, data: list[dict[str, Any]]) -> None:
        async with self._lock:
            self._results[task_id] = data

    async def get(self, task_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return self._results.get(task_id, [])

    async def query(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            all_items = []
            for items in self._results.values():
                all_items.extend(items)
            if filters:
                all_items = [
                    item for item in all_items
                    if all(item.get(k) == v for k, v in filters.items())
                ]
            return all_items[offset : offset + limit]

    async def clear(self) -> None:
        async with self._lock:
            self._results.clear()
