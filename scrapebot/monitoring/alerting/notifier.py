from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AlertNotifier:
    def __init__(self, webhook_url: str = "") -> None:
        self._webhook_url = webhook_url

    async def notify(self, title: str, message: str, severity: str = "warning") -> bool:
        if not self._webhook_url:
            logger.info("Alert [%s]: %s - %s", severity, title, message)
            return False

        payload = {
            "title": title,
            "message": message,
            "severity": severity,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                return resp.status_code < 400
        except Exception as exc:
            logger.error("Failed to send alert: %s", exc)
            return False
