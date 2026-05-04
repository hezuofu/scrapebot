"""StorageSink — final pipeline step that persists extracted data."""

from __future__ import annotations

import logging
from typing import Any

from scrapebot.pipeline.base import PipelineStep

logger = logging.getLogger(__name__)


class StorageSink(PipelineStep):
    """Wraps any BaseStorage adapter as the final pipeline step.

    On process(), saves all data items and emits storage events.
    """

    def __init__(self, storage: Any = None, collection: str = "default",
                 event_bus: Any = None) -> None:
        self._storage = storage
        self._collection = collection
        self._bus = event_bus

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        if self._storage is None:
            logger.warning("StorageSink: no storage adapter configured, data not persisted")
            return data

        items = data if isinstance(data, list) else [data] if data else []
        if not items:
            return data

        try:
            await self._storage.connect()
            count = await self._storage.save(items, self._collection)
            logger.info("StorageSink: saved %d items to %s", count, self._collection)

            if self._bus:
                from scrapebot.events.types import Event, EventType
                await self._bus.publish(Event(
                    type=EventType.STORAGE_SAVED,
                    message=f"Saved {count} items to {self._collection}",
                    data={"count": count, "collection": self._collection}))

        except Exception as exc:
            logger.error("StorageSink: save failed: %s", exc)
            if self._bus:
                from scrapebot.events.types import Event, EventType
                await self._bus.publish(Event(
                    type=EventType.STORAGE_FAILED,
                    message=str(exc), severity="error"))

        return data
