from __future__ import annotations

from typing import Any

from lxml import etree

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser


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
                    if result:
                        el = result[0]
                        item[field] = el.text_content().strip() if hasattr(el, "text_content") else str(el)
                    else:
                        item[field] = None
                items.append(item)
        else:
            item: dict[str, Any] = {}
            for field, xpath in selectors.items():
                result = tree.xpath(xpath)
                if result:
                    el = result[0]
                    item[field] = el.text_content().strip() if hasattr(el, "text_content") else str(el)
                else:
                    item[field] = None
                    errors.append(f"XPath '{xpath}' matched nothing for field '{field}'")
            items.append(item)

        return ParseResult(items=items, errors=errors)
