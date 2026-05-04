from __future__ import annotations

import re
from typing import Any

from scrapebot.pipeline.base import PipelineStep
from scrapebot.types import ParseResult


class FieldCleaner(PipelineStep):
    _PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
    _ID_CARD_RE = re.compile(r"\b\d{17}[\dXx]\b")
    _EMAIL_RE = re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b")

    def __init__(
        self,
        mask_phone: bool = False,
        mask_id_card: bool = False,
        mask_email: bool = False,
    ) -> None:
        self._mask_phone = mask_phone
        self._mask_id_card = mask_id_card
        self._mask_email = mask_email

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        if isinstance(data, ParseResult):
            items = data.items
        elif isinstance(data, list):
            items = data
        else:
            return data

        return [self._clean(item) if isinstance(item, dict) else item for item in items]

    def _clean(self, item: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, str):
                value = value.strip()
                value = " ".join(value.split())
                value = self._mask(value)
            result[key] = value
        return result

    def _mask(self, text: str) -> str:
        if self._mask_phone:
            text = self._PHONE_RE.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
        if self._mask_id_card:
            text = self._ID_CARD_RE.sub(lambda m: m.group()[:6] + "********" + m.group()[-4:], text)
        if self._mask_email:
            text = self._EMAIL_RE.sub(lambda m: m.group()[0] + "***@" + m.group().split("@")[1], text)
        return text
