from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from scrapebot.types import Task, TaskResult, TaskStatus

task_router = APIRouter()

_coordinator: Any = None


def set_coordinator(coordinator: Any) -> None:
    global _coordinator
    _coordinator = coordinator


@task_router.post("/", response_model=dict)
async def submit_task(task: Task) -> dict:
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    task_id = await _coordinator.submit(task)
    return {"task_id": task_id, "status": TaskStatus.PENDING}


@task_router.post("/batch", response_model=dict)
async def submit_batch(tasks: list[Task]) -> dict:
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    ids = await _coordinator.submit_batch(tasks)
    return {"task_ids": ids, "count": len(ids)}


@task_router.get("/{task_id}", response_model=dict)
async def get_task(task_id: str) -> dict:
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    result = _coordinator.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result.model_dump()


@task_router.delete("/{task_id}")
async def cancel_task(task_id: str) -> dict:
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    cancelled = await _coordinator.cancel(task_id)
    return {"task_id": task_id, "cancelled": cancelled}
