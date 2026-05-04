from __future__ import annotations

import json
import logging

import httpx

from scrapebot.events.types import Event

logger = logging.getLogger(__name__)

DEFAULT_NOTIFY_EVENTS = {
    "task.failed",
    "task.completed",
    "captcha.detected",
    "ban.detected",
    "circuit_breaker.open",
    "retry.exhausted",
    "anomaly.detected",
}


class WebhookSubscriber:
    def __init__(
        self,
        url: str = "",
        notify_events: set[str] | None = None,
        bus: object | None = None,
    ) -> None:
        self._url = url
        self._notify_events = notify_events or DEFAULT_NOTIFY_EVENTS
        if bus is not None and url:
            self.attach(bus)

    def attach(self, bus: object) -> None:
        bus.on_all(self.handle)

    async def handle(self, event: Event) -> None:
        if not self._url:
            return
        if event.type.value not in self._notify_events:
            return

        payload = {
            "event": event.type.value,
            "task_id": event.task_id,
            "message": event.message,
            "severity": event.severity,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(self._url, json=payload, timeout=10.0)
        except Exception:
            logger.debug("Webhook notification failed for %s", event.type.value)
