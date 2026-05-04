from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

    async def extract(self, instruction: str, content: str) -> list[dict[str, Any]]:
        self._ensure_client()

        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction assistant. Extract structured data as JSON. "
                    "Always return a JSON array of objects, even if there is only one item.",
                },
                {
                    "role": "user",
                    "content": f"Instruction: {instruction}\n\nContent:\n{content}",
                },
            ],
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "items" in data:
                    return data["items"]
                return [data]
            if isinstance(data, list):
                return data
            return [{"result": data}]
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
            return [{"raw": text}]

    async def classify(self, content: str, categories: list[str]) -> str:
        self._ensure_client()

        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=50,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": f"Classify this content into one of: {', '.join(categories)}.\n\nContent:\n{content[:4000]}",
                },
            ],
        )

        result = (response.choices[0].message.content or "").strip().lower()
        for cat in categories:
            if cat.lower() in result:
                return cat
        return result or "unknown"
