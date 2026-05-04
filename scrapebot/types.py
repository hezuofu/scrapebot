from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class ScrapeMode(str, Enum):
    FETCH = "fetch"
    RENDER = "render"
    AUTOMATE = "automate"


class DownloaderType(str, Enum):
    HTTP = "http"
    PLAYWRIGHT = "playwright"


class ParserType(str, Enum):
    CSS = "css"
    XPATH = "xpath"
    REGEX = "regex"
    LLM = "llm"
    COMPOSITE = "composite"
    NONE = "none"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    proxy: str | None = None
    scrape_mode: ScrapeMode = ScrapeMode.FETCH
    downloader_type: DownloaderType = DownloaderType.HTTP
    parser_type: ParserType = ParserType.CSS
    parser_instructions: dict[str, Any] = Field(default_factory=dict)
    automate_steps: list[dict[str, Any]] = Field(default_factory=list)
    priority: int = 0
    scheduled_at: datetime | None = None
    max_retries: int = 3
    timeout: float = 30.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class DownloadResult(BaseModel):
    url: str
    status_code: int = 0
    content: bytes = b""
    text: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    elapsed_ms: float = 0
    error: str | None = None
    screenshot: bytes | None = None

    class Config:
        arbitrary_types_allowed = True


class ParseResult(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    retry_count: int = 0
    download_result: DownloadResult | None = None
    parse_result: ParseResult | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class ScrapeConfig(BaseModel):
    rate_limit: float = 1.0
    concurrency: int = 5
    default_headers: dict[str, str] = Field(default_factory=dict)
    proxies: list[str] = Field(default_factory=list)
    max_retries: int = 3
    timeout: float = 30.0
    user_agents: list[str] = Field(default_factory=list)


class WorkerInfo(BaseModel):
    id: str
    host: str
    port: int
    status: str = "idle"
    current_task: str | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: datetime = Field(default_factory=datetime.now)
