from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DynamicSelector:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    async def generate_selectors(self, html: str, target_fields: list[str]) -> dict[str, str]:
        if self._llm is None:
            return {}
        try:
            return await self._llm.generate_selectors(html, target_fields)
        except Exception as exc:
            logger.error("Failed to generate selectors: %s", exc)
            return {}
