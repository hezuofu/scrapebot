from __future__ import annotations

from typing import Any

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser
from scrapebot.worker.parser.css_parser import CSSParser
from scrapebot.worker.parser.llm_parser import LLMParser
from scrapebot.worker.parser.regex_parser import RegexParser
from scrapebot.worker.parser.xpath_parser import XPathParser


class CompositeParser(BaseParser):
    def __init__(self) -> None:
        self._parsers: dict[str, BaseParser] = {
            "css": CSSParser(),
            "xpath": XPathParser(),
            "regex": RegexParser(),
            "llm": LLMParser(),
        }

    def set_llm_client(self, llm_client: Any) -> None:
        llm_parser = self._parsers.get("llm")
        if isinstance(llm_parser, LLMParser):
            llm_parser.set_client(llm_client)

    async def parse(self, html: str, instructions: dict[str, Any]) -> ParseResult:
        strategies: list[str] = instructions.get("strategies", ["css", "xpath", "regex"])
        all_items: list[dict[str, Any]] = []
        all_errors: list[str] = []

        for strategy in strategies:
            parser = self._parsers.get(strategy)
            if parser is None:
                continue
            result = await parser.parse(html, instructions)
            if result.items:
                all_items.extend(result.items)
                return ParseResult(items=all_items)
            all_errors.extend(result.errors)

        # Fallback to LLM if available
        if "llm" not in strategies and instructions.get("fallback_llm", False):
            result = await self._parsers["llm"].parse(html, instructions)
            if result.items:
                return result
            all_errors.extend(result.errors)

        return ParseResult(items=all_items, errors=all_errors)
