from __future__ import annotations

from typing import Any


class ContentSummarizer:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    async def summarize(self, content: str, max_length: int = 200) -> str:
        if self._llm is None:
            return content[:max_length]

        try:
            response = await self._llm._client.chat.completions.create(
                model=self._llm.model,
                max_tokens=max_length,
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this content in under {max_length} characters:\n\n{content[:3000]}",
                    },
                ],
            )
            return (response.choices[0].message.content or "")[:max_length]
        except Exception:
            return content[:max_length]

    async def classify(self, content: str, categories: list[str]) -> str:
        if self._llm is None:
            return "unknown"
        return await self._llm.classify(content, categories)
