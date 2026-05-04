from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, generate_latest


class PrometheusExporter:
    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(self, name: str, description: str = "", labels: list[str] | None = None) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, description, labels or [])
        return self._counters[name]

    def gauge(self, name: str, description: str = "", labels: list[str] | None = None) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description, labels or [])
        return self._gauges[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, description, labels or [], buckets=buckets)
        return self._histograms[name]

    def render(self) -> bytes:
        return generate_latest()
