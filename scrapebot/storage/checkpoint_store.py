from __future__ import annotations

import json
from typing import Any


class CheckpointStore:
    def __init__(self, file_path: str = "checkpoints.json") -> None:
        self._file_path = file_path
        self._checkpoints: dict[str, dict[str, Any]] = {}

    def save(self, task_id: str, state: dict[str, Any]) -> None:
        self._checkpoints[task_id] = state
        self._flush()

    def load(self, task_id: str) -> dict[str, Any] | None:
        return self._checkpoints.get(task_id)

    def remove(self, task_id: str) -> None:
        self._checkpoints.pop(task_id, None)
        self._flush()

    def list_checkpoints(self) -> list[str]:
        return list(self._checkpoints.keys())

    def _flush(self) -> None:
        with open(self._file_path, "w") as f:
            json.dump(self._checkpoints, f, default=str)
