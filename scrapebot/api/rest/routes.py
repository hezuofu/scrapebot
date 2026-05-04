from __future__ import annotations

from fastapi import APIRouter

from scrapebot.api.rest.config_api import config_router
from scrapebot.api.rest.stats_api import stats_router
from scrapebot.api.rest.task_api import task_router

router = APIRouter(prefix="/api/v1")
router.include_router(task_router, prefix="/tasks", tags=["tasks"])
router.include_router(stats_router, prefix="/stats", tags=["stats"])
router.include_router(config_router, prefix="/config", tags=["config"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
