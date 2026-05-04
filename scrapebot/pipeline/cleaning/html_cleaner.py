from __future__ import annotations

import re
from typing import Any


class HTMLCleaner:
    TAG_RE = re.compile(r"<[^>]+>")

    def clean(self, text: str) -> str:
        text = self.TAG_RE.sub(" ", text)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def clean_item(self, item: dict[str, Any], fields: list[str] | None = None) -> dict[str, Any]:
        target_fields = fields or list(item.keys())
        result = dict(item)
        for field in target_fields:
            if field in result and isinstance(result[field], str):
                result[field] = self.clean(result[field])
        return result
