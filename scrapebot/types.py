from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


# ── core enums ────────────────────────────────────────────

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


class PaginationType(str, Enum):
    NONE = "none"
    NEXT_LINK = "next_link"
    SCROLL = "scroll"
    PAGE_NUMBER = "page_number"


class FieldType(str, Enum):
    CSS = "css"
    XPATH = "xpath"
    REGEX = "regex"


class StorageType(str, Enum):
    FILE = "file"
    POSTGRES = "postgres"
    MONGODB = "mongodb"
    S3 = "s3"
    KAFKA = "kafka"


# ── runtime task model (unchanged core) ────────────────────

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


# ── result models ──────────────────────────────────────────

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


# ── infra models ───────────────────────────────────────────

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


# ── declarative scrape job models ──────────────────────────

class FieldSelector(BaseModel):
    """A single field to extract from a page."""
    name: str
    description: str = ""
    type: FieldType = FieldType.CSS
    selector: str  # CSS/XPath selector or source field for regex
    pattern: str | None = None   # regex pattern (required when type=regex)
    multiple: bool = False       # extract multiple values
    required: bool = False       # fail/flag if missing
    attribute: str | None = None # extract attribute instead of text


class PaginationConfig(BaseModel):
    type: PaginationType = PaginationType.NONE
    enabled: bool = False
    max_pages: int = 0    # 0 = unlimited
    delay: float = 1.0
    next_selector: str | None = None  # CSS for next_link or page_number
    page_param: str | None = None     # URL param name for page_number
    scroll_pixels: int = 800          # pixels per scroll for scroll type


class ScrapeRule(BaseModel):
    """A rule mapping a URL pattern to extraction + pagination."""
    url: str                                           # URL pattern (fnmatch)
    method: str = "GET"
    selectors: list[FieldSelector] = Field(default_factory=list)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    downloader: str = "http"                           # registry name
    scrape_mode: ScrapeMode = ScrapeMode.FETCH
    headers: dict[str, str] = Field(default_factory=dict)
    before_script: str | None = None                   # JS to run before extraction


class StorageRef(BaseModel):
    type: StorageType = StorageType.FILE
    file: dict[str, Any] | None = None      # { output_dir, format }
    postgres: dict[str, Any] | None = None  # { table, schema }
    mongodb: dict[str, Any] | None = None   # { collection, database }
    s3: dict[str, Any] | None = None        # { bucket, prefix }
    kafka: dict[str, Any] | None = None     # { topic }


class ScrapeJob(BaseModel):
    """A declarative scrape job — the high-level configuration format."""
    job_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""
    start_urls: list[str] = Field(default_factory=list)
    rules: list[ScrapeRule] = Field(default_factory=list)
    concurrency: int = 1
    download_delay: float = 1.0
    max_retries: int = 3
    timeout: float = 30.0
    headers: dict[str, str] = Field(default_factory=dict)
    proxy: str | None = None
    storage: StorageRef | None = None

    # ── convenience ────────────────────────────────────────

    def selectors_for_url(self, url: str) -> list[FieldSelector]:
        """Return the selectors from the first rule matching this URL."""
        from fnmatch import fnmatch as _fnmatch
        for rule in self.rules:
            if _fnmatch(url, rule.url):
                return rule.selectors
        return []

    def rule_for_url(self, url: str) -> ScrapeRule | None:
        from fnmatch import fnmatch as _fnmatch
        for rule in self.rules:
            if _fnmatch(url, rule.url):
                return rule
        return None
