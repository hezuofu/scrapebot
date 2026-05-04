from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_RETRYING = "task.retrying"

    DOWNLOAD_STARTED = "download.started"
    DOWNLOAD_COMPLETED = "download.completed"
    DOWNLOAD_FAILED = "download.failed"

    PARSE_STARTED = "parse.started"
    PARSE_COMPLETED = "parse.completed"
    PARSE_FAILED = "parse.failed"

    AUTOMATE_STEP_STARTED = "automate.step.started"
    AUTOMATE_STEP_COMPLETED = "automate.step.completed"
    AUTOMATE_STEP_FAILED = "automate.step.failed"

    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_STEP_STARTED = "pipeline.step.started"
    PIPELINE_STEP_COMPLETED = "pipeline.step.completed"

    STORAGE_SAVED = "storage.saved"
    STORAGE_FAILED = "storage.failed"

    CAPTCHA_DETECTED = "captcha.detected"
    BAN_DETECTED = "ban.detected"
    RATE_LIMITED = "rate.limited"
    PROXY_SWITCHED = "proxy.switched"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker.open"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker.closed"

    RETRY_ATTEMPT = "retry.attempt"
    RETRY_EXHAUSTED = "retry.exhausted"

    WORKER_REGISTERED = "worker.registered"
    WORKER_UNREGISTERED = "worker.unregistered"
    WORKER_HEARTBEAT = "worker.heartbeat"
    WORKER_STALE = "worker.stale"

    CHECKPOINT_SAVED = "checkpoint.saved"
    CHECKPOINT_LOADED = "checkpoint.loaded"

    ANOMALY_DETECTED = "anomaly.detected"
    ALERT_TRIGGERED = "alert.triggered"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: EventType
    task_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    data: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    severity: str = "info"
