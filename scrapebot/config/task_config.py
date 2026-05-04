from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scrapebot.types import DownloaderType, ParserType, ScrapeMode


@dataclass
class TaskTemplate:
    name: str
    description: str = ""
    scrape_mode: ScrapeMode = ScrapeMode.FETCH
    downloader_type: DownloaderType = DownloaderType.HTTP
    parser_type: ParserType = ParserType.CSS
    parser_instructions: dict[str, Any] = field(default_factory=dict)
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit: float = 1.0
    proxy_required: bool = False
    javascript: bool = False
    automate_steps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskConfig:
    templates: dict[str, TaskTemplate] = field(default_factory=dict)
    default_timeout: float = 30.0
    default_max_retries: int = 3
    default_rate_limit: float = 1.0
    default_scrape_mode: ScrapeMode = ScrapeMode.FETCH
    max_concurrent_tasks: int = 100
    task_queue_max_size: int = 10000
    result_ttl_seconds: int = 86400
    batch_size_limit: int = 1000


DEFAULT_TASK_CONFIG = TaskConfig(
    templates={
        "static_page": TaskTemplate(
            name="static_page",
            description="Simple static HTML page scraping",
            scrape_mode=ScrapeMode.FETCH,
            downloader_type=DownloaderType.HTTP,
            parser_type=ParserType.CSS,
        ),
        "spa_page": TaskTemplate(
            name="spa_page",
            description="Single-page application with JavaScript rendering",
            scrape_mode=ScrapeMode.RENDER,
            downloader_type=DownloaderType.PLAYWRIGHT,
            parser_type=ParserType.CSS,
            javascript=True,
            timeout=60.0,
        ),
        "automate_form": TaskTemplate(
            name="automate_form",
            description="Form interaction and data extraction via browser automation",
            scrape_mode=ScrapeMode.AUTOMATE,
            downloader_type=DownloaderType.PLAYWRIGHT,
            parser_type=ParserType.COMPOSITE,
            javascript=True,
            timeout=90.0,
        ),
        "ai_extract": TaskTemplate(
            name="ai_extract",
            description="AI-powered content extraction using LLM",
            scrape_mode=ScrapeMode.FETCH,
            downloader_type=DownloaderType.HTTP,
            parser_type=ParserType.LLM,
            timeout=60.0,
        ),
    },
)
