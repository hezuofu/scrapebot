from __future__ import annotations

import pytest

from scrapebot.scheduler.queue.priority_queue import PriorityQueue
from scrapebot.scheduler.queue.delayed_queue import DelayedQueue
from scrapebot.types import Task


@pytest.mark.asyncio
async def test_priority_queue_ordering():
    q = PriorityQueue()
    await q.push(Task(url="http://low.com", priority=10))
    await q.push(Task(url="http://high.com", priority=0))
    await q.push(Task(url="http://mid.com", priority=5))

    first = await q.pop()
    second = await q.pop()
    third = await q.pop()

    assert first.priority == 0
    assert second.priority == 5
    assert third.priority == 10


@pytest.mark.asyncio
async def test_priority_queue_empty_pop():
    q = PriorityQueue()
    result = await q.pop()
    assert result is None


@pytest.mark.asyncio
async def test_priority_queue_size():
    q = PriorityQueue()
    assert await q.size() == 0
    await q.push(Task(url="http://test.com"))
    assert await q.size() == 1


@pytest.mark.asyncio
async def test_priority_queue_remove():
    q = PriorityQueue()
    task = Task(url="http://remove.com")
    await q.push(task)
    removed = await q.remove(task.id)
    assert removed is True
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_priority_queue_clear():
    q = PriorityQueue()
    await q.push(Task(url="http://1.com"))
    await q.push(Task(url="http://2.com"))
    await q.clear()
    assert await q.size() == 0


@pytest.mark.asyncio
async def test_delayed_queue_immediate():
    q = DelayedQueue()
    task = Task(url="http://now.com")
    await q.push(task)
    popped = await q.pop()
    assert popped is not None
    assert popped.url == "http://now.com"
