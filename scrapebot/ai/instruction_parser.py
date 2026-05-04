from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InstructionParser:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    async def parse_natural_language(self, instruction: str) -> dict[str, Any]:
        if self._llm is None:
            logger.warning("No LLM client configured for instruction parsing")
            return {"error": "No LLM client configured"}

        # Check cache first
        cached = self._llm.get_cached_instruction(instruction)
        if cached:
            return cached

        try:
            result = await self._llm.extract(
                f"Convert this scraping instruction into structured config: {instruction}",
                instruction,
            )
            parsed = result[0] if result else {}
            self._llm.cache_instruction(instruction, parsed)
            return parsed
        except Exception as exc:
            logger.error("Failed to parse instruction: %s", exc)
            return {"error": str(exc)}
