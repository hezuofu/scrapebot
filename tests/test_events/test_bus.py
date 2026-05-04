from __future__ import annotations

import asyncio

import pytest

from scrapebot.events.bus import EventBus
from scrapebot.events.types import Event, EventType


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    bus = EventBus()
    received = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.TASK_CREATED, handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1", message="hello"))
    assert len(received) == 1
    assert received[0].task_id == "t1"
    assert received[0].message == "hello"


@pytest.mark.asyncio
async def test_on_all_handler():
    bus = EventBus()
    received = []

    async def catch_all(event: Event) -> None:
        received.append(event)

    bus.on_all(catch_all)
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
    await bus.publish(Event(type=EventType.TASK_COMPLETED, task_id="t1"))
    assert len(received) == 2


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.TASK_CREATED, handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t1"))
    bus.unsubscribe(EventType.TASK_CREATED, handler)
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="t2"))
    assert len(received) == 1


@pytest.mark.asyncio
async def test_get_history():
    bus = EventBus()
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="a"))
    await bus.publish(Event(type=EventType.TASK_COMPLETED, task_id="a"))
    await bus.publish(Event(type=EventType.TASK_CREATED, task_id="b"))

    history_a = bus.get_history(task_id="a")
    assert len(history_a) == 2

    history_created = bus.get_history(event_type=EventType.TASK_CREATED)
    assert len(history_created) == 2


@pytest.mark.asyncio
async def test_wait_for():
    bus = EventBus()

    async def delayed_publish() -> None:
        await asyncio.sleep(0.1)
        await bus.publish(Event(type=EventType.TASK_COMPLETED, task_id="done"))

    asyncio.create_task(delayed_publish())
    event = await bus.wait_for(EventType.TASK_COMPLETED, task_id="done", timeout=1.0)
    assert event is not None
    assert event.task_id == "done"


@pytest.mark.asyncio
async def test_wait_for_timeout():
    bus = EventBus()
    event = await bus.wait_for(EventType.TASK_COMPLETED, timeout=0.1)
    assert event is None


def test_event_type_values():
    assert EventType.TASK_CREATED == "task.created"
    assert EventType.DOWNLOAD_STARTED == "download.started"
    assert EventType.CAPTCHA_DETECTED == "captcha.detected"
    assert EventType.BAN_DETECTED == "ban.detected"


def test_event_creation():
    event = Event(
        type=EventType.TASK_CREATED,
        task_id="test-123",
        message="Hello",
        data={"url": "https://example.com"},
    )
    assert event.id is not None
    assert event.type == EventType.TASK_CREATED
    assert event.task_id == "test-123"
    assert event.severity == "info"
