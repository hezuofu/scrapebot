"""Local file storage — the default output adapter."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage

JSONL_GZ_AVAILABLE = False
try:
    import gzip as _gzip
    JSONL_GZ_AVAILABLE = True
except ImportError:
    pass


class LocalFileStorage(BaseStorage):
    def __init__(self, output_dir: str = "output", format: str = "json") -> None:
        self._output_dir = Path(output_dir)
        self._format = format
        self._current_file: str | None = None
        self._items_written = 0

    async def connect(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def disconnect(self) -> None:
        pass

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        if not data:
            return 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{collection}_{timestamp}.{self._format}"
        filepath = self._output_dir / filename

        if self._format == "json":
            return self._write_json(filepath, data)
        elif self._format == "jsonl":
            return self._write_jsonl(filepath, data)
        elif self._format == "jsonl.gz":
            return self._write_jsonl_gz(filepath, data)
        else:
            return self._write_json(filepath, data)

    def _write_json(self, path: Path, data: list[dict[str, Any]]) -> int:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return len(data)

    def _write_jsonl(self, path: Path, data: list[dict[str, Any]]) -> int:
        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
                count += 1
        return count

    def _write_jsonl_gz(self, path: Path, data: list[dict[str, Any]]) -> int:
        if not JSONL_GZ_AVAILABLE:
            return self._write_jsonl(path, data)
        count = 0
        with _gzip.open(path, "wt", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
                count += 1
        return count

    async def query(
        self,
        collection: str = "default",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        pattern = f"{collection}_*.{self._format}"
        files = sorted(self._output_dir.glob(pattern), reverse=True)

        for filepath in files:
            if len(results) >= offset + limit:
                break
            items = self._read_file(filepath)
            if filters:
                items = [i for i in items if all(i.get(k) == v for k, v in filters.items())]
            results.extend(items)

        return results[offset:offset + limit]

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        try:
            if path.suffix == ".json":
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else [data]
            elif path.suffix == ".gz":
                with _gzip.open(path, "rt", encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
            else:
                with open(path, encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
        except Exception:
            return []

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        deleted = 0
        pattern = f"{collection}_*.{self._format}"
        for filepath in self._output_dir.glob(pattern):
            try:
                os.remove(filepath)
                deleted += 1
            except OSError:
                pass
        return deleted
