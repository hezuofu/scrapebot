from __future__ import annotations

from typing import Any

from scrapebot.pipeline.base import PipelineStep


class DataTransformer(PipelineStep):
    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._mapping = mapping or {}

    async def process(
        self,
        data: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if isinstance(data, list):
            return [self._transform_item(item) for item in data]
        return [self._transform_item(data)]

    def _transform_item(self, item: dict[str, Any]) -> dict[str, Any]:
        if not self._mapping:
            return item
        transformed: dict[str, Any] = {}
        for src, dst in self._mapping.items():
            transformed[dst] = item.get(src)
        return transformed
