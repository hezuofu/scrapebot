from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredLogger:
    def __init__(self, name: str = "scrapebot", level: str = "INFO") -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        self._logger.addHandler(handler)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(msg, extra={"fields": kwargs})

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(msg, extra={"fields": kwargs})

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(msg, extra={"fields": kwargs})

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(msg, extra={"fields": kwargs})

    def get_logger(self) -> logging.Logger:
        return self._logger


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", {})
        if fields:
            data["fields"] = fields
        if record.exc_info and record.exc_info[0]:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)
