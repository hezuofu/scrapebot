from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DynamicSelector:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    async def generate_selectors(
        self,
        html: str,
        target_fields: list[str],
    ) -> dict[str, str]:
        if self._llm is None:
            return {}

        snippet = html[:6000]
        fields_desc = ", ".join(target_fields)

        prompt = (
            f"Given this HTML snippet, generate CSS selectors to extract: {fields_desc}. "
            "Return JSON: {\"field_name\": \"css_selector\", ...}. "
            "Use the most specific and reliable selectors possible."
        )

        try:
            response = await self._llm._client.chat.completions.create(
                model=self._llm.model,
                max_tokens=1024,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\nHTML:\n{snippet}"},
                ],
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
        except Exception as exc:
            logger.error("Failed to generate selectors: %s", exc)
            return {}
