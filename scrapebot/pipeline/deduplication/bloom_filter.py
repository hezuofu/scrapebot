from __future__ import annotations

import math
from typing import Any

import xxhash


class BloomFilter:
    def __init__(self, capacity: int = 100_000, error_rate: float = 0.001) -> None:
        self._size = int(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        self._hash_count = int(self._size / capacity * math.log(2))
        self._bits = bytearray(math.ceil(self._size / 8))

    def add(self, item: Any) -> None:
        key = str(item).encode()
        for seed in range(self._hash_count):
            idx = xxhash.xxh64(key, seed=seed).intdigest() % self._size
            self._bits[idx // 8] |= 1 << (idx % 8)

    def contains(self, item: Any) -> bool:
        key = str(item).encode()
        for seed in range(self._hash_count):
            idx = xxhash.xxh64(key, seed=seed).intdigest() % self._size
            if not (self._bits[idx // 8] & (1 << (idx % 8))):
                return False
        return True

    def add_if_new(self, item: Any) -> bool:
        if self.contains(item):
            return False
        self.add(item)
        return True
