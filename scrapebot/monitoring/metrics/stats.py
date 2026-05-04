from __future__ import annotations

import time
from collections import defaultdict


class StatsTracker:
    def __init__(self) -> None:
        self._start_time = time.monotonic()
        self.tasks_submitted = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.bytes_downloaded = 0
        self._response_times: list[float] = []
        self._errors_by_type: dict[str, int] = defaultdict(int)
        self._status_codes: dict[int, int] = defaultdict(int)

    def record_completed(self, response_time_ms: float, bytes_count: int, status_code: int = 200) -> None:
        self.tasks_completed += 1
        self._response_times.append(response_time_ms)
        self.bytes_downloaded += bytes_count
        self._status_codes[status_code] += 1

    def record_failed(self, error_type: str) -> None:
        self.tasks_failed += 1
        self._errors_by_type[error_type] += 1

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 1.0
        return self.tasks_completed / total

    @property
    def avg_response_time(self) -> float:
        if not self._response_times:
            return 0
        return sum(self._response_times) / len(self._response_times)

    def snapshot(self) -> dict:
        return {
            "uptime_seconds": round(self.uptime_seconds, 2),
            "tasks_submitted": self.tasks_submitted,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": round(self.success_rate, 4),
            "bytes_downloaded": self.bytes_downloaded,
            "avg_response_time_ms": round(self.avg_response_time, 2),
            "errors_by_type": dict(self._errors_by_type),
            "status_codes": dict(self._status_codes),
        }
