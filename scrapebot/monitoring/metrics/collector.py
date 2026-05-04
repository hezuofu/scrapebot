from __future__ import annotations

import time
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._timers: dict[str, float] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

    def start_timer(self, name: str) -> str:
        timer_id = f"{name}:{time.monotonic()}"
        self._timers[timer_id] = time.monotonic()
        return timer_id

    def stop_timer(self, timer_id: str) -> float:
        start = self._timers.pop(timer_id, time.monotonic())
        elapsed = time.monotonic() - start
        name = timer_id.split(":")[0]
        self.observe(name, elapsed * 1000)
        return elapsed * 1000

    def get_all(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "avg": sum(v) / len(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self._histograms.items()
            },
        }
