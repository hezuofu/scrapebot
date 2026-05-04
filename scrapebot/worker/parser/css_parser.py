from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from scrapebot.types import ParseResult
from scrapebot.worker.parser.base import BaseParser


class CSSParser(BaseParser):
    async def parse(self, html: str, instructions: dict[str, Any]) -> ParseResult:
        soup = BeautifulSoup(html, "lxml")
        items: list[dict[str, Any]] = []
        errors: list[str] = []

        selectors: dict[str, str] = instructions.get("selectors", {})
        if not selectors:
            return ParseResult(items=items, errors=["No CSS selectors provided"])

        if instructions.get("extract_list", False):
            rows = soup.select(instructions.get("list_selector", "body > *"))
            for row in rows:
                item: dict[str, Any] = {}
                for field, css in selectors.items():
                    if css.startswith("& "):
                        el = row.select_one(css[2:])
                    else:
                        el = soup.select_one(css)
                    if el:
                        attr = instructions.get("attributes", {}).get(field)
                        item[field] = el.get(attr) if attr else el.get_text(strip=True)
                    else:
                        item[field] = None
                items.append(item)
        else:
            item: dict[str, Any] = {}
            for field, css in selectors.items():
                el = soup.select_one(css)
                if el:
                    attr = instructions.get("attributes", {}).get(field)
                    item[field] = el.get(attr) if attr else el.get_text(strip=True)
                else:
                    item[field] = None
                    errors.append(f"Selector '{css}' matched nothing for field '{field}'")
            items.append(item)

        return ParseResult(items=items, errors=errors)
