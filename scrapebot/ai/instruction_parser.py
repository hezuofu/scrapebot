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

        prompt = (
            "Convert the following natural language scraping instruction into a structured configuration. "
            "Output JSON with these fields: selectors (dict of field->css_selector), "
            "extract_list (bool), list_selector (string|null), parser_type (css|xpath|regex|llm), "
            "attributes (dict of field->html_attribute|null).\n\n"
            f"Instruction: {instruction}"
        )

        try:
            response = await self._llm._client.chat.completions.create(
                model=self._llm.model,
                max_tokens=1024,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:
            logger.error("Failed to parse instruction: %s", exc)
            return {"error": str(exc)}
