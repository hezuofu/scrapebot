from __future__ import annotations

import logging
from typing import Any

import httpx

from scrapebot.types import TaskResult

logger = logging.getLogger(__name__)


class WebhookCallback:
    def __init__(self, url: str = "") -> None:
        self._url = url

    async def send(self, result: TaskResult) -> bool:
        if not self._url:
            return False

        payload = {
            "task_id": result.task_id,
            "status": result.status.value,
            "data": result.data,
            "error": result.error,
            "items_count": len(result.data),
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._url, json=payload, timeout=10.0)
                if resp.status_code >= 400:
                    logger.warning("Webhook callback failed: %d", resp.status_code)
                    return False
                return True
        except Exception as exc:
            logger.error("Webhook callback error: %s", exc)
            return False
