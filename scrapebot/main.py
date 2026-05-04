"""
Scrapebot - Distributed web scraping framework.

Every component is configurable and replaceable via the Registry.

Usage:
    python -m scrapebot.main              # Standalone mode
    python -m scrapebot.main --api        # Start REST API server
    scrapebot                             # Via Poetry script

Custom components:
    from scrapebot.registry import get_registry
    reg = get_registry()
    reg.register("downloader", "my_custom", lambda **kw: MyDownloader(**kw))
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import uvicorn

from scrapebot.config.settings import load_settings, Settings
from scrapebot.config.store import ConfigStore
from scrapebot.events.bus import EventBus
from scrapebot.events.types import EventType
from scrapebot.events.subscribers.logger import LoggingSubscriber
from scrapebot.events.subscribers.metrics import MetricsSubscriber
from scrapebot.events.subscribers.webhook import WebhookSubscriber
from scrapebot.middleware.chain import MiddlewareChain
from scrapebot.monitoring.logging.structured import StructuredLogger
from scrapebot.monitoring.metrics.stats import StatsTracker
from scrapebot.pipeline.base import Pipeline
from scrapebot.registry import get_registry, Registry
from scrapebot.scheduler.coordinator import Coordinator
from scrapebot.scheduler.dispatcher import Dispatcher
from scrapebot.scheduler.load_balancer import LoadBalancer
from scrapebot.storage.task_store import TaskStore
from scrapebot.types import Task
from scrapebot.worker.downloader.selector import DownloaderSelector
from scrapebot.worker.executor import Executor

logger = logging.getLogger("scrapebot")


def _build_middleware(settings: Settings, registry: Registry) -> MiddlewareChain | None:
    """Build middleware chain from registry with action trigger wired to detectors."""
    from scrapebot.middleware.anti_detect.action_trigger import ActionTrigger

    rate_limiter = registry.create("middleware", "rate_limiter",
        requests_per_second=settings.rate_limit.requests_per_second,
        burst_size=settings.rate_limit.burst_size)
    ua = registry.create("middleware", "ua_rotator")
    fp = registry.create("middleware", "fingerprint")

    trigger = ActionTrigger(settings)
    captcha = registry.create("middleware", "captcha_detector", trigger=trigger)
    ban = registry.create("middleware", "ban_detector", trigger=trigger)

    proxy_rotator = registry.create("middleware", "proxy_rotator",
        proxies=[], rotation="round_robin",
        sticky=settings.proxy_config.session_sticky)

    retry = registry.create("middleware", "retry_policy",
        max_attempts=settings.retry.max_attempts,
        backoff_base=settings.retry.backoff_base,
        backoff_max=settings.retry.backoff_max)

    return MiddlewareChain(
        rate_limiter=rate_limiter,
        enrichers=[ua, fp],
        retry_policy=retry,
        post_processors=[captcha, ban, trigger],
        proxy_enabled=settings.proxy_config.enabled,
        proxy_rotator=proxy_rotator,
    )


def create_app(
    settings: Settings | None = None,
    config_store: ConfigStore | None = None,
    registry: Registry | None = None,
):
    if settings is None:
        settings = load_settings()
    if registry is None:
        registry = get_registry()

    bus = EventBus()

    # Event subscribers
    LoggingSubscriber(bus)
    stats = StatsTracker()
    MetricsSubscriber(stats, bus)
    if settings.monitoring.alert_webhook:
        WebhookSubscriber(settings.monitoring.alert_webhook, bus=bus)

    # Config persistence
    if config_store is None:
        config_store = ConfigStore()
        config_store.load_all()

    # ── resolve components from registry ─────────────────────

    queue = registry.create("queue", settings.scheduler.queue)

    downloader_selector = DownloaderSelector(
        http_downloader=registry.create("downloader", "http"),
        playwright_downloader=registry.create("downloader", "playwright",
            headless=settings.worker.playwright_headless,
            pool_size=settings.worker.playwright_pool_size),
        browser_automator=registry.create("downloader", "automator",
            headless=settings.worker.playwright_headless),
        site_rules=settings.site_rules,
    )

    parser = registry.create("parser", settings.worker.parser)

    pipeline = Pipeline()
    for step_name in settings.worker.pipeline_steps:
        pipeline.add(registry.create("pipeline_step", step_name))

    # ── storage sink (final pipeline step) ────────────────────
    storage_type = getattr(settings.storage_config, "default_output", "file")
    storage_adapter = registry.create("storage", storage_type,
        output_dir="output", format="json")
    from scrapebot.pipeline.storage_sink import StorageSink
    pipeline.add(StorageSink(storage=storage_adapter, collection="scrape_results", event_bus=bus))

    executor = Executor(
        settings,
        event_bus=bus,
        downloader_selector=downloader_selector,
        parser=parser,
        pipeline=pipeline,
        max_concurrency=settings.scheduler.max_concurrent_tasks,
        middleware_chain=_build_middleware(settings, registry),
    )

    dispatcher = Dispatcher(settings, executor=executor)
    load_balancer = LoadBalancer(settings)
    task_store = TaskStore(settings.storage_config.redis.url)

    coordinator = Coordinator(
        settings,
        queue=queue,
        dispatcher=dispatcher,
        load_balancer=load_balancer,
        event_bus=bus,
        task_store=task_store,
    )

    # ── webhook callback on task completion ───────────────────
    webhook_url = getattr(settings.storage_config, "default_output", None)
    if settings.monitoring.alert_webhook:
        from scrapebot.api.webhook.callback import WebhookCallback
        _wh = WebhookCallback(settings.monitoring.alert_webhook)
        async def _on_task_done(event):
            result = coordinator.get_result(event.task_id)
            if result:
                await _wh.send(result)
        bus.subscribe(EventType.TASK_COMPLETED, _on_task_done)
        bus.subscribe(EventType.TASK_FAILED, _on_task_done)

    # Wire LLM client into parsers that need it
    if settings.llm.api_key:
        from scrapebot.ai.llm_client import LLMClient
        llm_client = LLMClient(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
            model=settings.llm.model,
            max_tokens=settings.llm.max_tokens,
            temperature=settings.llm.temperature,
        )
        if hasattr(parser, "set_llm_client"):
            parser.set_llm_client(llm_client)

    return coordinator, task_store, stats, load_balancer, bus, config_store, registry


async def run_standalone(settings: Settings, test_url: str | None = None) -> None:
    coordinator, task_store, stats, _, bus, config_store, registry = create_app(settings)

    if test_url:
        task = Task(url=test_url)
        task_id = await coordinator.submit(task)
        logger.info("Submitted: %s (mode=%s)", task_id, task.scrape_mode.value)
        await coordinator.start()
        result = coordinator.get_result(task_id)
        if result:
            logger.info("Result: status=%s items=%d", result.status.value, len(result.data))
    else:
        logger.info("Scrapebot standalone — use --api for REST server.")


def run_api(settings: Settings) -> None:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from scrapebot.api.rest.routes import router

    app = FastAPI(
        title="Scrapebot API",
        description="Pluggable distributed web scraping framework",
        version="0.4.0",
    )
    app.include_router(router)

    coordinator, task_store, stats, load_balancer, bus, config_store, registry = create_app(settings)

    from scrapebot.api.rest.config_api import set_config_store
    from scrapebot.api.rest.task_api import set_coordinator
    from scrapebot.api.rest.stats_api import set_stats_tracker, set_load_balancer

    set_coordinator(coordinator)
    set_stats_tracker(stats)
    set_load_balancer(load_balancer)
    set_config_store(config_store)

    static_dir = Path(__file__).parent / "api" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/dashboard/static", StaticFiles(directory=str(static_dir)), name="dashboard_static")

    @app.get("/dashboard")
    async def dashboard():
        from fastapi.responses import FileResponse
        return FileResponse(static_dir / "dashboard.html")

    @app.get("/metrics")
    async def metrics():
        from prometheus_client import generate_latest
        return await asyncio.to_thread(generate_latest)

    @app.get("/")
    async def root():
        return {
            "app": "Scrapebot",
            "version": "0.4.0",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "api": "/api/v1",
            "metrics": "/metrics",
            "registry": {c: registry.list(c) for c in registry.categories()},
        }

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.create_task(coordinator.start())
        logger.info("API: http://%s:%d  Dashboard: http://%s:%d/dashboard",
                     settings.api.host, settings.api.port, settings.api.host, settings.api.port)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await config_store.save_all()
        await coordinator.stop()

    uvicorn.run(app, host=settings.api.host, port=settings.api.port,
                log_level=settings.monitoring.log_level.lower())


def run() -> None:
    parser = argparse.ArgumentParser(description="Scrapebot — Pluggable web scraping framework")
    parser.add_argument("--api", action="store_true", help="Start the REST API server")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML file")
    parser.add_argument("--url", type=str, default=None, help="Test URL to scrape")
    parser.add_argument("--mode", type=str, choices=["fetch", "render", "automate"],
                        default="fetch", help="Scrape mode for test URL")
    parser.add_argument("--list-components", action="store_true", help="List registered components")
    args = parser.parse_args()

    settings = load_settings(args.config)

    if args.list_components:
        StructuredLogger(level="WARNING")
        reg = get_registry()
        for cat in reg.categories():
            print(f"\n{cat}:")
            for name in reg.list(cat):
                meta = reg.describe(cat, name)
                print(f"  {name:20s} — {meta.get('description', '')}")
        return

    StructuredLogger(level=settings.monitoring.log_level)

    if args.api:
        run_api(settings)
    else:
        asyncio.run(run_standalone(settings, test_url=args.url))


if __name__ == "__main__":
    run()
