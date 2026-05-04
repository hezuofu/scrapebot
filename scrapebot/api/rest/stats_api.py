from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

stats_router = APIRouter()

_stats_tracker: Any = None
_load_balancer: Any = None


def set_stats_tracker(tracker: Any) -> None:
    global _stats_tracker
    _stats_tracker = tracker


def set_load_balancer(lb: Any) -> None:
    global _load_balancer
    _load_balancer = lb


@stats_router.get("/")
async def get_stats() -> dict:
    if _stats_tracker is None:
        raise HTTPException(status_code=503, detail="Stats not initialized")
    return _stats_tracker.snapshot()


@stats_router.get("/workers")
async def get_workers() -> list[dict]:
    if _load_balancer is None:
        return []
    workers = await _load_balancer.get_workers()
    return [w.model_dump() for w in workers]
