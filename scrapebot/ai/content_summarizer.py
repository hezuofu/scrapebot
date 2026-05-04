from __future__ import annotations

from typing import Any


class ContentSummarizer:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    async def summarize(self, content: str, max_length: int = 200) -> str:
        if self._llm is None:
            return content[:max_length]
        try:
            result = await self._llm.extract(
                f"Summarize in under {max_length} characters",
                content[:3000],
            )
            text = str(result[0].get("summary", result[0]) if result else "")
            return text[:max_length] if text else content[:max_length]
        except Exception:
            return content[:max_length]

    async def classify(self, content: str, categories: list[str]) -> str:
        if self._llm is None:
            return "unknown"
        return await self._llm.classify(content, categories)
