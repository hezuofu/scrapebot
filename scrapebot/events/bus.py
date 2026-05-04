from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from scrapebot.events.types import Event, EventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Coroutine[Any, Any, None]] | Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_subscribers: list[EventHandler] = []
        self._history: list[Event] = []
        self._history_max: int = 1000
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        key = event_type.value if isinstance(event_type, EventType) else event_type
        self._subscribers[key].append(handler)

    def on_all(self, handler: EventHandler) -> None:
        self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        key = event_type.value if isinstance(event_type, EventType) else event_type
        try:
            self._subscribers[key].remove(handler)
        except ValueError:
            pass
        try:
            self._global_subscribers.remove(handler)
        except ValueError:
            pass

    async def publish(self, event: Event) -> None:
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max:]

        await self._notify(event.type.value, event)
        for handler in self._global_subscribers:
            await self._invoke(handler, event)

    async def _notify(self, event_key: str, event: Event) -> None:
        handlers = self._subscribers.get(event_key, [])
        for handler in handlers:
            await self._invoke(handler, event)

    async def _invoke(self, handler: EventHandler, event: Event) -> None:
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("Event handler %s failed for event %s", handler, event.type)

    def get_history(
        self,
        event_type: EventType | str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        results = self._history
        if event_type:
            key = event_type.value if isinstance(event_type, EventType) else event_type
            results = [e for e in results if e.type.value == key]
        if task_id:
            results = [e for e in results if e.task_id == task_id]
        return results[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    async def wait_for(
        self,
        event_type: EventType | str,
        task_id: str | None = None,
        timeout: float = 30.0,
    ) -> Event | None:
        key = event_type.value if isinstance(event_type, EventType) else event_type
        future: asyncio.Future[Event] = asyncio.get_event_loop().create_future()

        async def handler(event: Event) -> None:
            if task_id and event.task_id != task_id:
                return
            if not future.done():
                future.set_result(event)

        self.subscribe(event_type, handler)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(event_type, handler)
