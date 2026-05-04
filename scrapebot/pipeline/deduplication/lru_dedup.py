from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any


class LRUDedup:
    def __init__(self, max_size: int = 10_000) -> None:
        self._cache: OrderedDict[str, None] = OrderedDict()
        self._max_size = max_size

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
