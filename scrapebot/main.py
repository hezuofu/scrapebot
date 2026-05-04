"""
Scrapebot - Distributed web scraping framework.

Three scrape modes:
  - fetch:    HTTP request → HTML → local parse (fast, lightweight)
  - render:   Browser render → HTML → local parse (JavaScript SPAs)
  - automate: Browser automation → direct extraction (clicks, scrolls, forms)

Usage:
    python -m scrapebot.main              # Standalone mode
    python -m scrapebot.main --api        # Start REST API server
    scrapebot                             # Via Poetry script
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import uvicorn

from scrapebot.config.settings import load_settings, Settings
from scrapebot.config.store import ConfigStore
from scrapebot.events.bus import EventBus, get_event_bus
from scrapebot.events.subscribers.logger import LoggingSubscriber
from scrapebot.events.subscribers.metrics import MetricsSubscriber
from scrapebot.events.subscribers.webhook import WebhookSubscriber
from scrapebot.monitoring.logging.structured import StructuredLogger
from scrapebot.monitoring.metrics.stats import StatsTracker
from scrapebot.scheduler.coordinator import Coordinator
from scrapebot.scheduler.dispatcher import Dispatcher
from scrapebot.scheduler.load_balancer import LoadBalancer
from scrapebot.scheduler.queue.priority_queue import PriorityQueue
from scrapebot.storage.task_store import TaskStore
from scrapebot.types import ScrapeMode, Task
from scrapebot.worker.executor import Executor

logger = logging.getLogger("scrapebot")


def create_app(settings: Settings | None = None, config_store: ConfigStore | None = None):
    if settings is None:
        settings = load_settings()

    bus = get_event_bus()

    # Wire built-in event subscribers
    LoggingSubscriber(bus)
    stats = StatsTracker()
    MetricsSubscriber(stats, bus)
    if settings.monitoring.alert_webhook:
        WebhookSubscriber(settings.monitoring.alert_webhook, bus=bus)

    # Config persistence
    if config_store is None:
        config_store = ConfigStore()
        config_store.load_all()

    queue = PriorityQueue()
    executor = Executor(settings, event_bus=bus)
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

    # Wire LLM client if configured
    if settings.llm.api_key:
        from scrapebot.ai.llm_client import LLMClient

        llm_client = LLMClient(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
            model=settings.llm.model,
            max_tokens=settings.llm.max_tokens,
            temperature=settings.llm.temperature,
        )
        executor._parser.set_llm_client(llm_client)

    return coordinator, task_store, stats, load_balancer, bus, config_store


async def run_standalone(settings: Settings, test_url: str | None = None) -> None:
    coordinator, task_store, stats, _, bus, config_store = create_app(settings)

    if test_url:
        task = Task(url=test_url)
        task_id = await coordinator.submit(task)
        logger.info("Submitted test task: %s (mode=%s)", task_id, task.scrape_mode.value)

        await coordinator.start()
        result = coordinator.get_result(task_id)
        if result:
            logger.info("Result: status=%s items=%d", result.status.value, len(result.data))
    else:
        logger.info("Scrapebot standalone mode — submit tasks via API or programmatically.")
        logger.info("Use --api flag to start the REST API server.")


def run_api(settings: Settings) -> None:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from scrapebot.api.rest.routes import router

    app = FastAPI(
        title="Scrapebot API",
        description="Distributed web scraping framework with config dashboard",
        version="0.3.0",
    )
    app.include_router(router)

    coordinator, task_store, stats, load_balancer, bus, config_store = create_app(settings)

    # Wire config API
    from scrapebot.api.rest.config_api import set_config_store
    from scrapebot.api.rest.task_api import set_coordinator
    from scrapebot.api.rest.stats_api import set_stats_tracker, set_load_balancer

    set_coordinator(coordinator)
    set_stats_tracker(stats)
    set_load_balancer(load_balancer)
    set_config_store(config_store)

    # Serve config dashboard as static files
    static_dir = Path(__file__).parent / "api" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/dashboard/static", StaticFiles(directory=str(static_dir)), name="dashboard_static")

    @app.get("/dashboard")
    async def dashboard():
        from fastapi.responses import FileResponse
        return FileResponse(static_dir / "dashboard.html")

    @app.get("/")
    async def root():
        return {
            "app": "Scrapebot",
            "version": "0.3.0",
            "docs": "/docs",
            "dashboard": "/dashboard",
            "api": "/api/v1",
        }

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.create_task(coordinator.start())
        logger.info("API server: http://%s:%d", settings.api.host, settings.api.port)
        logger.info("Dashboard: http://%s:%d/dashboard", settings.api.host, settings.api.port)
        logger.info("API docs: http://%s:%d/docs", settings.api.host, settings.api.port)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await config_store.save_all()
        await coordinator.stop()
        logger.info("API server stopped — configs saved")

    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        log_level=settings.monitoring.log_level.lower(),
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Scrapebot — Distributed web scraping framework")
    parser.add_argument("--api", action="store_true", help="Start the REST API server")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML file")
    parser.add_argument("--url", type=str, default=None, help="Test URL to scrape (standalone)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fetch", "render", "automate"],
        default="fetch",
        help="Scrape mode for test URL",
    )
    args = parser.parse_args()

    settings = load_settings(args.config)
    StructuredLogger(level=settings.monitoring.log_level)

    if args.api:
        run_api(settings)
    else:
        asyncio.run(run_standalone(settings, test_url=args.url))


if __name__ == "__main__":
    run()
