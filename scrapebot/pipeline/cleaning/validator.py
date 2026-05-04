from __future__ import annotations

from typing import Any

from scrapebot.pipeline.base import PipelineStep


class DataValidator(PipelineStep):
    async def process(
        self,
        data: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if isinstance(data, list):
            return [item for item in data if self._is_valid(item)]
        return data

    def _is_valid(self, item: Any) -> bool:
        if item is None:
            return False
        if isinstance(item, dict):
            return any(v is not None and v != "" for v in item.values())
        return True
