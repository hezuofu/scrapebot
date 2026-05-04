from __future__ import annotations

import re
from typing import Any

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser


class RegexParser(BaseParser):
    async def parse(self, html: str, instructions: dict[str, Any]) -> ParseResult:
        items: list[dict[str, Any]] = []
        errors: list[str] = []

        patterns: dict[str, str] = instructions.get("patterns", {})
        if not patterns:
            return ParseResult(items=items, errors=["No regex patterns provided"])

        item: dict[str, Any] = {}
        for field, pattern in patterns.items():
            flags = re.DOTALL | re.MULTILINE
            match = re.search(pattern, html, flags)
            if match:
                if match.groups():
                    item[field] = match.group(1)
                else:
                    item[field] = match.group(0)
            else:
                item[field] = None
                errors.append(f"Pattern '{pattern}' matched nothing for field '{field}'")
        items.append(item)

        return ParseResult(items=items, errors=errors)
