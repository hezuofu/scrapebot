from __future__ import annotations

import logging

from scrapebot.events.types import Event

logger = logging.getLogger("scrapebot.events")


class LoggingSubscriber:
    def __init__(self, bus: object | None = None) -> None:
        if bus is not None:
            self.attach(bus)

    def attach(self, bus: object) -> None:
        bus.on_all(self.handle)

    async def handle(self, event: Event) -> None:
        level = logging.WARNING if event.severity == "warning" else logging.INFO
        if event.severity == "error":
            level = logging.ERROR

        logger.log(
            level,
            "[%s] %s  task_id=%s",
            event.type.value,
            event.message,
            event.task_id,
        )
