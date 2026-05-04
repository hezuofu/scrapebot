from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointStore:
    def __init__(self, file_path: str = "checkpoints.json") -> None:
        self._file_path = Path(file_path)
        self._checkpoints: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._lock = asyncio.Lock()

    async def save(self, task_id: str, state: dict[str, Any]) -> None:
        async with self._lock:
            self._checkpoints[task_id] = state
            self._dirty = True

    async def load(self, task_id: str) -> dict[str, Any] | None:
        async with self._lock:
            if not self._checkpoints and self._file_path.exists():
                await self._read_from_disk()
        return self._checkpoints.get(task_id)

    async def remove(self, task_id: str) -> None:
        async with self._lock:
            self._checkpoints.pop(task_id, None)
            self._dirty = True

    async def list_checkpoints(self) -> list[str]:
        async with self._lock:
            return list(self._checkpoints.keys())

    async def flush(self) -> None:
        async with self._lock:
            if not self._dirty:
                return
            await self._write_to_disk()
            self._dirty = False

    async def _write_to_disk(self) -> None:
        try:
            data = json.dumps(self._checkpoints, default=str)
            await asyncio.to_thread(self._sync_write, data)
        except Exception as exc:
            logger.error("Failed to write checkpoint file: %s", exc)

    def _sync_write(self, data: str) -> None:
        with open(self._file_path, "w", encoding="utf-8") as f:
            f.write(data)

    async def _read_from_disk(self) -> None:
        try:
            data = await asyncio.to_thread(self._sync_read)
            self._checkpoints.update(data)
        except Exception as exc:
            logger.error("Failed to read checkpoint file: %s", exc)

    def _sync_read(self) -> dict[str, Any]:
        if not self._file_path.exists():
            return {}
        with open(self._file_path, encoding="utf-8") as f:
            return json.load(f)
