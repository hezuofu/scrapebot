from __future__ import annotations

from typing import Any

from lxml import etree

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser


def _join_results(result: list) -> str:
    parts: list[str] = []
    for el in result:
        if hasattr(el, "text_content"):
            parts.append(el.text_content().strip())
        elif isinstance(el, str):
            parts.append(el.strip())
        else:
            parts.append(str(el))
    return " ".join(p for p in parts if p)


class XPathParser(BaseParser):
    async def parse(self, html: str, instructions: dict[str, Any]) -> ParseResult:
        try:
            tree = etree.HTML(html)
        except Exception as exc:
            return ParseResult(errors=[f"Failed to parse HTML: {exc}"])

        items: list[dict[str, Any]] = []
        errors: list[str] = []

        selectors: dict[str, str] = instructions.get("selectors", {})
        if not selectors:
            return ParseResult(items=items, errors=["No XPath selectors provided"])

        if instructions.get("extract_list", False):
            list_xpath = instructions.get("list_selector", "//body/*")
            rows = tree.xpath(list_xpath)
            for row in rows:
                item: dict[str, Any] = {}
                for field, xpath in selectors.items():
                    result = row.xpath(xpath) if xpath.startswith(".") else tree.xpath(xpath)
                    item[field] = _join_results(result) if result else None
                items.append(item)
        else:
            item: dict[str, Any] = {}
            for field, xpath in selectors.items():
                result = tree.xpath(xpath)
                if result:
                    item[field] = _join_results(result)
                else:
                    item[field] = None
                    errors.append(f"XPath '{xpath}' matched nothing for field '{field}'")
            items.append(item)

        return ParseResult(items=items, errors=errors)
