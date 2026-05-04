from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any


class JaegerTracer:
    def __init__(self, endpoint: str = "", service_name: str = "scrapebot") -> None:
        self._endpoint = endpoint
        self._service_name = service_name
        self._active_spans: dict[str, dict] = {}

    @asynccontextmanager
    async def span(self, name: str, tags: dict[str, Any] | None = None):
        span_id = f"{name}:{time.monotonic()}"
        span = {
            "name": name,
            "start_time": time.monotonic(),
            "tags": tags or {},
        }
        self._active_spans[span_id] = span
        try:
            yield span
        finally:
            span["duration_ms"] = (time.monotonic() - span["start_time"]) * 1000
            self._active_spans.pop(span_id, None)
