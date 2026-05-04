from __future__ import annotations

from scrapebot.events.types import Event, EventType


class MetricsSubscriber:
    def __init__(self, stats_tracker: object | None = None, bus: object | None = None) -> None:
        self._stats = stats_tracker
        if bus is not None and stats_tracker is not None:
            self.attach(bus)

    def attach(self, bus: object) -> None:
        bus.on_all(self.handle)

    async def handle(self, event: Event) -> None:
        if self._stats is None:
            return

        event_type = event.type

        if event_type == EventType.TASK_CREATED:
            self._stats.tasks_submitted += 1
        elif event_type == EventType.TASK_COMPLETED:
            self._stats.tasks_completed += 1
        elif event_type == EventType.TASK_FAILED:
            self._stats.tasks_failed += 1
        elif event_type == EventType.TASK_RETRYING:
            self._stats.tasks_submitted += 1
        elif event_type == EventType.DOWNLOAD_COMPLETED:
            elapsed = event.data.get("elapsed_ms", 0)
            size = event.data.get("bytes", 0)
            if elapsed:
                self._stats.record_completed(elapsed, size)
        elif event_type == EventType.DOWNLOAD_FAILED:
            self._stats.record_failed("download")
        elif event_type == EventType.CAPTCHA_DETECTED:
            self._stats.record_failed("captcha")
        elif event_type == EventType.BAN_DETECTED:
            self._stats.record_failed("ban")
