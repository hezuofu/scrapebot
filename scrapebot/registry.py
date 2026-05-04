"""
Pluggable component registry.

Every component (downloader, parser, queue, storage, pipeline step,
middleware) is registered by name and resolved at runtime from
configuration. Users can register custom implementations.

Usage:
    reg = Registry()
    reg.register("downloader", "http", lambda **kw: HTTPDownloader(**kw))
    downloader = reg.create("downloader", "http", timeout=30)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
Factory = Callable[..., Any]


class RegistryError(Exception):
    """Raised when a component cannot be resolved."""


class Registry:
    def __init__(self) -> None:
        self._factories: dict[str, dict[str, Factory]] = defaultdict(dict)
        self._metadata: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)

    def register(
        self,
        category: str,
        name: str,
        factory: Factory,
        *,
        description: str = "",
        replace: bool = False,
    ) -> None:
        if name in self._factories[category] and not replace:
            raise RegistryError(
                f"Component '{name}' already registered in category '{category}'. "
                f"Use replace=True to override."
            )
        self._factories[category][name] = factory
        self._metadata[category][name] = {"description": description}

    def create(self, category: str, name: str, **kwargs: Any) -> Any:
        if name not in self._factories.get(category, {}):
            available = self.list(category)
            raise RegistryError(
                f"Unknown component '{name}' in category '{category}'. "
                f"Available: {available}"
            )
        try:
            return self._factories[category][name](**kwargs)
        except Exception as exc:
            raise RegistryError(
                f"Failed to create '{name}' in category '{category}': {exc}"
            ) from exc

    def create_chain(
        self,
        category: str,
        names: list[str],
        shared_kwargs: dict[str, Any] | None = None,
        per_instance_kwargs: dict[str, dict[str, Any]] | None = None,
    ) -> list[Any]:
        shared = shared_kwargs or {}
        per = per_instance_kwargs or {}
        instances = []
        for name in names:
            kwargs = {**shared, **per.get(name, {})}
            instances.append(self.create(category, name, **kwargs))
        return instances

    def list(self, category: str) -> list[str]:
        return sorted(self._factories.get(category, {}).keys())

    def categories(self) -> list[str]:
        return sorted(self._factories.keys())

    def describe(self, category: str, name: str) -> dict[str, str]:
        return dict(self._metadata.get(category, {}).get(name, {}))

    def unregister(self, category: str, name: str) -> bool:
        removed = self._factories.get(category, {}).pop(name, None) is not None
        self._metadata.get(category, {}).pop(name, None)
        return removed


# ── global singleton ──────────────────────────────────────

_registry: Registry | None = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
        _register_all_builtins(_registry)
    return _registry


def reset_registry() -> Registry:
    global _registry
    _registry = Registry()
    _register_all_builtins(_registry)
    return _registry


def _register_all_builtins(reg: Registry) -> None:
    """Auto-discover and register all built-in components."""
    from scrapebot.scheduler.queue.priority_queue import PriorityQueue
    from scrapebot.scheduler.queue.delayed_queue import DelayedQueue
    from scrapebot.scheduler.queue.redis_queue import RedisQueue

    reg.register("queue", "priority", lambda **kw: PriorityQueue(),
                 description="In-memory priority queue using heapq")
    reg.register("queue", "delayed", lambda **kw: DelayedQueue(),
                 description="Queue with delayed/scheduled task support")
    reg.register("queue", "redis", lambda **kw: RedisQueue(**kw),
                 description="Redis-backed distributed queue")

    from scrapebot.worker.downloader.http_downloader import HTTPDownloader
    from scrapebot.worker.downloader.playwright_downloader import PlaywrightDownloader
    from scrapebot.worker.downloader.browser_automator import BrowserAutomator

    reg.register("downloader", "http", lambda **kw: HTTPDownloader(**kw),
                 description="Lightweight httpx-based downloader")
    reg.register("downloader", "playwright", lambda **kw: PlaywrightDownloader(**kw),
                 description="Browser-based downloader for JavaScript SPAs")
    reg.register("downloader", "automator", lambda **kw: BrowserAutomator(**kw),
                 description="Full browser automation (click, scroll, type, extract)")

    from scrapebot.worker.parser.css_parser import CSSParser
    from scrapebot.worker.parser.xpath_parser import XPathParser
    from scrapebot.worker.parser.regex_parser import RegexParser
    from scrapebot.worker.parser.llm_parser import LLMParser
    from scrapebot.worker.parser.composite_parser import CompositeParser

    reg.register("parser", "css", lambda **kw: CSSParser(),
                 description="CSS selector-based HTML parser")
    reg.register("parser", "xpath", lambda **kw: XPathParser(),
                 description="XPath-based HTML/XML parser")
    reg.register("parser", "regex", lambda **kw: RegexParser(),
                 description="Regex-based text parser")
    reg.register("parser", "llm", lambda **kw: LLMParser(**kw),
                 description="LLM-powered intelligent parser")
    reg.register("parser", "composite", lambda **kw: CompositeParser(),
                 description="Multi-strategy parser with CSS→XPath→Regex→LLM fallback")

    from scrapebot.pipeline.storage.postgres import PostgresStorage
    from scrapebot.pipeline.storage.mongodb import MongoStorage
    from scrapebot.pipeline.storage.s3 import S3Storage
    from scrapebot.pipeline.storage.kafka import KafkaStorage
    from scrapebot.pipeline.storage.local_file import LocalFileStorage

    reg.register("storage", "file", lambda **kw: LocalFileStorage(**kw),
                 description="Local file storage (JSON/JSONL)")
    reg.register("storage", "postgres", lambda **kw: PostgresStorage(**kw),
                 description="PostgreSQL storage adapter")
    reg.register("storage", "mongodb", lambda **kw: MongoStorage(**kw),
                 description="MongoDB storage adapter")
    reg.register("storage", "s3", lambda **kw: S3Storage(**kw),
                 description="AWS S3 / OSS storage adapter")
    reg.register("storage", "kafka", lambda **kw: KafkaStorage(**kw),
                 description="Apache Kafka streaming adapter")

    from scrapebot.pipeline.cleaning.field_cleaner import FieldCleaner
    from scrapebot.pipeline.cleaning.html_cleaner import HTMLCleaner
    from scrapebot.pipeline.cleaning.validator import DataValidator
    from scrapebot.pipeline.transformer import DataTransformer
    from scrapebot.pipeline.deduplication.bloom_filter import BloomFilter
    from scrapebot.pipeline.deduplication.lru_dedup import LRUDedup
    from scrapebot.pipeline.deduplication.redis_dedup import RedisDedup

    reg.register("pipeline_step", "field_cleaner", lambda **kw: FieldCleaner(),
                 description="Strip whitespace, normalize fields")
    reg.register("pipeline_step", "html_cleaner", lambda **kw: HTMLCleaner(),
                 description="Strip HTML tags from text fields")
    reg.register("pipeline_step", "validator", lambda **kw: DataValidator(),
                 description="Filter out empty/null items")
    reg.register("pipeline_step", "transformer", lambda **kw: DataTransformer(**kw),
                 description="Field mapping and renaming")
    reg.register("pipeline_step", "bloom_dedup", lambda **kw: BloomFilter(**kw),
                 description="Bloom filter for memory-efficient deduplication")
    reg.register("pipeline_step", "lru_dedup", lambda **kw: LRUDedup(**kw),
                 description="LRU cache for bounded-memory deduplication")
    reg.register("pipeline_step", "redis_dedup", lambda **kw: RedisDedup(**kw),
                 description="Redis-backed distributed deduplication")

    from scrapebot.middleware.rate_limiter import RateLimiter
    from scrapebot.middleware.headers.ua_rotator import UARotator
    from scrapebot.middleware.headers.fingerprint import BrowserFingerprint
    from scrapebot.middleware.proxy.rotator import ProxyRotator
    from scrapebot.middleware.retry.retry_policy import RetryPolicy
    from scrapebot.middleware.retry.circuit_breaker import CircuitBreaker
    from scrapebot.middleware.anti_detect.captcha_detector import CaptchaDetector
    from scrapebot.middleware.anti_detect.ban_detector import BanDetector
    from scrapebot.middleware.anti_detect.action_trigger import ActionTrigger

    reg.register("middleware", "rate_limiter", lambda **kw: RateLimiter(**kw),
                 description="Token-bucket rate limiter")
    reg.register("middleware", "ua_rotator", lambda **kw: UARotator(**kw),
                 description="User-Agent rotation")
    reg.register("middleware", "fingerprint", lambda **kw: BrowserFingerprint(),
                 description="Browser fingerprint header enrichment")
    reg.register("middleware", "proxy_rotator", lambda **kw: ProxyRotator(**kw),
                 description="Proxy pool rotation (round-robin/random)")
    reg.register("middleware", "retry_policy", lambda **kw: RetryPolicy(**kw),
                 description="Exponential backoff retry")
    reg.register("middleware", "circuit_breaker", lambda **kw: CircuitBreaker(**kw),
                 description="Circuit breaker for failing hosts")
    reg.register("middleware", "captcha_detector", lambda **kw: CaptchaDetector(),
                 description="Detect captcha challenges in responses")
    reg.register("middleware", "ban_detector", lambda **kw: BanDetector(),
                 description="Detect IP bans and rate-limit blocks")
    reg.register("middleware", "action_trigger", lambda **kw: ActionTrigger(**kw),
                 description="Trigger counter-actions on captcha/ban detection")
