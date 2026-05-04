from __future__ import annotations

import json
import os
from datetime import datetime


class LogStorage:
    def __init__(self, base_dir: str = "logs", max_file_size_mb: int = 100) -> None:
        self._base_dir = base_dir
        self._max_size = max_file_size_mb * 1024 * 1024
        os.makedirs(base_dir, exist_ok=True)

    def write(self, record: dict) -> None:
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self._base_dir, f"scrapebot-{date}.jsonl")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        if os.path.getsize(log_file) > self._max_size:
            self._rotate(date)

    def _rotate(self, date: str) -> None:
        log_file = os.path.join(self._base_dir, f"scrapebot-{date}.jsonl")
        timestamp = datetime.now().strftime("%H%M%S")
        rotated = os.path.join(self._base_dir, f"scrapebot-{date}-{timestamp}.jsonl")
        os.rename(log_file, rotated)
