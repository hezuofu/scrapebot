from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from scrapebot.types import TaskResult

logger = logging.getLogger(__name__)


class WebhookCallback:
    def __init__(self, url: str = "", max_retries: int = 3, backoff_base: float = 2.0) -> None:
        self._url = url
        self._max_retries = max_retries
        self._backoff_base = backoff_base

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

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(self._url, json=payload, timeout=10.0)
                    if resp.status_code < 400:
                        return True
                    logger.warning("Webhook attempt %d/%d: HTTP %d", attempt, self._max_retries, resp.status_code)
            except Exception as exc:
                logger.warning("Webhook attempt %d/%d: %s", attempt, self._max_retries, exc)

            if attempt < self._max_retries:
                delay = self._backoff_base ** attempt
                await asyncio.sleep(delay)

        logger.error("Webhook failed after %d attempts for task %s", self._max_retries, result.task_id)
        return False
