from __future__ import annotations

from typing import Any

from scrapebot.pipeline.base import PipelineStep


class DataValidator(PipelineStep):
    def __init__(
        self,
        required_fields: list[str] | None = None,
        field_types: dict[str, str] | None = None,
        field_ranges: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self._required = required_fields or []
        self._types = field_types or {}
        self._ranges = field_ranges or {}

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        if isinstance(data, list):
            return [item for item in data if self._is_valid(item)]
        return data

    def _is_valid(self, item: Any) -> bool:
        if item is None:
            return False
        if not isinstance(item, dict):
            return True

        for field in self._required:
            v = item.get(field)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                return False

        for field, expected_type in self._types.items():
            v = item.get(field)
            if v is None:
                continue
            if expected_type == "number":
                try:
                    float(str(v))
                except (ValueError, TypeError):
                    return False
            elif expected_type == "integer":
                try:
                    int(str(v))
                except (ValueError, TypeError):
                    return False

        for field, (lo, hi) in self._ranges.items():
            v = item.get(field)
            if v is None:
                continue
            try:
                n = float(v)
                if n < lo or n > hi:
                    return False
            except (ValueError, TypeError):
                return False

        return any(v is not None and v != "" for v in item.values())
