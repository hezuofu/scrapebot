from __future__ import annotations

from typing import Any

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser


class LLMParser(BaseParser):
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    def set_client(self, llm_client: Any) -> None:
        self._llm = llm_client

    async def parse(self, html: str, instructions: dict[str, Any]) -> ParseResult:
        if self._llm is None:
            return ParseResult(errors=["LLM client not configured"])

        prompt = instructions.get("prompt", "Extract structured data from this HTML content.")
        max_length = instructions.get("max_html_length", 8000)

        truncated = html[:max_length]
        if len(html) > max_length:
            truncated += f"\n\n[HTML truncated, original length: {len(html)} chars]"

        try:
            response = await self._llm.extract(prompt, truncated)
            if isinstance(response, list):
                return ParseResult(items=response)
            elif isinstance(response, dict):
                return ParseResult(items=[response])
            else:
                return ParseResult(items=[{"raw": response}])
        except Exception as exc:
            return ParseResult(errors=[f"LLM parsing failed: {exc}"])
