from __future__ import annotations

import csv
import io
import json
from typing import Any

from scrapebot.pipeline.base import PipelineStep


class DataTransformer(PipelineStep):
    def __init__(
        self,
        mapping: dict[str, str] | None = None,
        aggregate: bool = False,
        aggregate_key: str = "",
        output_format: str = "",
    ) -> None:
        self._mapping = mapping or {}
        self._aggregate = aggregate
        self._aggregate_key = aggregate_key
        self._output_format = output_format

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        if isinstance(data, list):
            items = [self._transform_item(item) if isinstance(item, dict) else item for item in data]
        else:
            items = [self._transform_item(data) if isinstance(data, dict) else data]

        if self._aggregate and self._aggregate_key and items:
            items = self._aggregate_items(items)

        if self._output_format == "csv" and items:
            return self._to_csv(items)
        if self._output_format == "json" and items:
            return self._to_json(items)

        return items

    def _transform_item(self, item: dict[str, Any]) -> dict[str, Any]:
        if not self._mapping:
            return item
        transformed: dict[str, Any] = {dst: item.get(src) for src, dst in self._mapping.items()}
        return transformed

    def _aggregate_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for item in items:
            key = str(item.get(self._aggregate_key, ""))
            if key not in groups:
                groups[key] = dict(item)
            else:
                for k, v in item.items():
                    if k != self._aggregate_key:
                        existing = groups[key].get(k)
                        if isinstance(existing, list):
                            existing.append(v)
                        else:
                            groups[key][k] = [existing, v] if existing is not None else [v]
        return list(groups.values())

    @staticmethod
    def _to_csv(items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(items)
        return output.getvalue()

    @staticmethod
    def _to_json(items: list[dict[str, Any]]) -> str:
        return json.dumps(items, ensure_ascii=False, indent=2, default=str)
