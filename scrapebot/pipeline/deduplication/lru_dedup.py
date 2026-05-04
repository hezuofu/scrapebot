from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any


from scrapebot.pipeline.base import PipelineStep


class LRUDedup(PipelineStep):
    def __init__(self, max_size: int = 10_000) -> None:
        self._cache: OrderedDict[str, None] = OrderedDict()
        self._max_size = max_size

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        if isinstance(data, list):
            return [item for item in data if not self.is_duplicate(item)]
        return None if self.is_duplicate(data) else data

    def is_duplicate(self, item: Any) -> bool:
        key = self._digest(item)
        if key in self._cache:
            self._cache.move_to_end(key)
            return True

        self._cache[key] = None
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return False

    def clear(self) -> None:
        self._cache.clear()

    @staticmethod
    def _digest(item: Any) -> str:
        return hashlib.sha256(str(item).encode()).hexdigest()
