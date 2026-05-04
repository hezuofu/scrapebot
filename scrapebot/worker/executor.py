from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from scrapebot.config.settings import Settings
from scrapebot.events.bus import EventBus
from scrapebot.events.types import Event, EventType
from scrapebot.pipeline.base import Pipeline
from scrapebot.types import (
    DownloadResult,
    ScrapeMode,
    Task,
    TaskResult,
    TaskStatus,
)
from scrapebot.worker.downloader.selector import DownloaderSelector
from scrapebot.worker.parser.base import BaseParser

logger = logging.getLogger(__name__)


class Executor:
    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus,
        downloader_selector: DownloaderSelector | None = None,
        parser: BaseParser | None = None,
        pipeline: Pipeline | None = None,
        max_concurrency: int | None = None,
        middleware_chain: Any = None,
    ) -> None:
        self.settings = settings
        self._bus = event_bus
        self._selector = downloader_selector or DownloaderSelector(site_rules=settings.site_rules)
        self._parser = parser
        self._pipeline = pipeline or Pipeline()
        self._semaphore = asyncio.Semaphore(max_concurrency or settings.scheduler.max_concurrent_tasks)
        self._middleware = middleware_chain

    async def execute(self, task: Task) -> TaskResult:
        handler = self._execute_inner
        if self._middleware:
            handler = self._middleware.wrap(handler)

        async with self._semaphore:
            try:
                result = await asyncio.wait_for(handler(task), timeout=task.timeout)
            except asyncio.TimeoutError:
                logger.error("Task %s timed out after %.1fs", task.id, task.timeout)
                await self._emit(EventType.TASK_FAILED, task, "Task timed out", "error")
                return TaskResult(
                    task_id=task.id, status=TaskStatus.FAILED,
                    error=f"Timeout after {task.timeout}s",
                    started_at=datetime.now(), finished_at=datetime.now())
            return result

    async def _execute_inner(self, task: Task) -> TaskResult:
        await self._emit(EventType.TASK_STARTED, task)

        try:
            download_result = await self._run_download(task)
            if download_result.error:
                return self._failure(task, download_result.error, download_result)
            return await self._parse_and_complete(task, download_result)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Task %s failed: %s", task.id, exc)
            await self._emit(EventType.TASK_FAILED, task, str(exc), "error")
            return TaskResult(
                task_id=task.id, status=TaskStatus.FAILED, error=str(exc),
                started_at=datetime.now(), finished_at=datetime.now())

    async def _run_download(self, task: Task) -> DownloadResult:
        await self._emit(EventType.DOWNLOAD_STARTED, task)
        downloader = self._selector.select_downloader(task)
        result = await downloader.download(
            task.url,
            headers=task.headers,
            proxy=task.proxy,
            timeout=task.timeout,
            steps=task.automate_steps or None,
        )
        if result.error:
            await self._emit(EventType.DOWNLOAD_FAILED, task, result.error, "error")
        else:
            await self._emit(EventType.DOWNLOAD_COMPLETED, task,
                data={"status_code": result.status_code, "bytes": len(result.content)})
        return result

    async def _parse_and_complete(self, task: Task, download_result: DownloadResult) -> TaskResult:
        now = datetime.now()

        await self._emit(EventType.PARSE_STARTED, task)
        if self._parser is not None:
            parse_result = await self._parser.parse(download_result.text, task.parser_instructions)
        else:
            from scrapebot.types import ParseResult
            parse_result = ParseResult(items=[{"content": download_result.text}])

        if parse_result.errors:
            await self._emit(EventType.PARSE_FAILED, task, data={"errors": parse_result.errors}, severity="warning")
        else:
            await self._emit(EventType.PARSE_COMPLETED, task)

        await self._emit(EventType.PIPELINE_STARTED, task)
        pipeline_result = await self._pipeline.run(parse_result, context={"task": task})
        await self._emit(EventType.PIPELINE_COMPLETED, task)

        data = pipeline_result if isinstance(pipeline_result, list) else parse_result.items
        await self._emit(EventType.TASK_COMPLETED, task)
        # Report result for downloader fallback learning
        await self._selector.report_result(task, download_result)
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            data=data,
            started_at=now,
            finished_at=datetime.now(),
            download_result=download_result,
            parse_result=parse_result,
        )

    def _failure(self, task: Task, error: str, download_result: DownloadResult | None = None) -> TaskResult:
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.FAILED,
            error=error,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            download_result=download_result,
        )

    async def _emit(
        self,
        event_type: EventType,
        task: Task,
        message: str = "",
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        await self._bus.publish(Event(
            type=event_type,
            task_id=task.id,
            message=message,
            severity=severity,
            data=data or {},
        ))

    async def close(self) -> None:
        await self._selector.close()
