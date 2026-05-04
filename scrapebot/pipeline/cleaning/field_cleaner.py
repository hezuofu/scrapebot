from __future__ import annotations

from typing import Any

from scrapebot.pipeline.base import PipelineStep


class FieldCleaner(PipelineStep):
    async def process(
        self,
        data: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if hasattr(data, "items"):
            items = data.items
        elif isinstance(data, list):
            items = data
        else:
            return data

        cleaned = []
        for item in items:
            if isinstance(item, dict):
                cleaned.append(self._clean(item))
            else:
                cleaned.append(item)
        return cleaned

    def _clean(self, item: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, str):
                value = value.strip()
                value = " ".join(value.split())
            result[key] = value
        return result
