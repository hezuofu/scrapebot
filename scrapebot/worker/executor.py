from __future__ import annotations

import logging
from datetime import datetime

from scrapebot.config.settings import Settings
from scrapebot.events.bus import EventBus, get_event_bus
from scrapebot.events.types import Event, EventType
from scrapebot.pipeline.base import Pipeline
from scrapebot.pipeline.cleaning.field_cleaner import FieldCleaner
from scrapebot.pipeline.cleaning.validator import DataValidator
from scrapebot.types import (
    DownloadResult,
    ParseResult,
    ScrapeMode,
    Task,
    TaskResult,
    TaskStatus,
)
from scrapebot.worker.downloader.selector import DownloaderSelector
from scrapebot.worker.parser.composite_parser import CompositeParser

logger = logging.getLogger(__name__)


class Executor:
    def __init__(
        self,
        settings: Settings,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings = settings
        self._bus = event_bus or get_event_bus()
        self._downloader_selector = DownloaderSelector(site_rules=settings.site_rules)
        self._parser = CompositeParser()
        self._pipeline = Pipeline()
        self._pipeline.add(FieldCleaner()).add(DataValidator())

    async def execute(self, task: Task) -> TaskResult:
        started_at = datetime.now()
        events: list[dict] = []

        await self._emit(EventType.TASK_STARTED, task, "Task started")

        try:
            if task.scrape_mode == ScrapeMode.AUTOMATE:
                result = await self._execute_automate(task, events)
            else:
                result = await self._execute_fetch_or_render(task, events)
        except Exception as exc:
            logger.error("Task %s failed: %s", task.id, exc)
            await self._emit(EventType.TASK_FAILED, task, str(exc), "error")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=str(exc),
                started_at=started_at,
                finished_at=datetime.now(),
                events=events,
            )

        result.events = events
        return result

    async def _execute_fetch_or_render(
        self,
        task: Task,
        events: list[dict],
    ) -> TaskResult:
        started_at = datetime.now()

        await self._emit(EventType.DOWNLOAD_STARTED, task, f"Downloading {task.url}")
        downloader = self._downloader_selector.select(task)
        download_result = await downloader.download(
            task.url,
            headers=task.headers,
            proxy=task.proxy,
            timeout=task.timeout,
        )

        if download_result.error:
            await self._emit(EventType.DOWNLOAD_FAILED, task, download_result.error, "error")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=download_result.error,
                started_at=started_at,
                finished_at=datetime.now(),
                download_result=download_result,
                events=events,
            )

        await self._emit(
            EventType.DOWNLOAD_COMPLETED,
            task,
            f"Downloaded {len(download_result.content)} bytes, status={download_result.status_code}",
            data={"status_code": download_result.status_code, "bytes": len(download_result.content)},
        )

        await self._emit(EventType.PARSE_STARTED, task, "Parsing content")
        parse_result = await self._parser.parse(
            download_result.text,
            task.parser_instructions,
        )

        if parse_result.errors:
            await self._emit(
                EventType.PARSE_FAILED,
                task,
                f"Parse errors: {parse_result.errors}",
                "warning",
                data={"errors": parse_result.errors},
            )
        else:
            await self._emit(
                EventType.PARSE_COMPLETED,
                task,
                f"Parsed {len(parse_result.items)} items",
            )

        await self._emit(EventType.PIPELINE_STARTED, task, "Running pipeline")
        pipeline_result = await self._pipeline.run(
            parse_result,
            context={"task": task},
        )
        await self._emit(EventType.PIPELINE_COMPLETED, task, "Pipeline complete")

        await self._emit(EventType.TASK_COMPLETED, task, f"Task completed: {len(parse_result.items)} items")
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            data=pipeline_result if isinstance(pipeline_result, list) else parse_result.items,
            started_at=started_at,
            finished_at=datetime.now(),
            download_result=download_result,
            parse_result=parse_result,
            events=events,
        )

    async def _execute_automate(
        self,
        task: Task,
        events: list[dict],
    ) -> TaskResult:
        started_at = datetime.now()
        automator = self._downloader_selector.get_automator()

        await self._emit(EventType.AUTOMATE_STEP_STARTED, task, "Starting browser automation")

        download_result = await automator.execute(
            task.url,
            steps=task.automate_steps,
            headers=task.headers,
            proxy=task.proxy,
            timeout=task.timeout,
        )

        if download_result.error:
            await self._emit(EventType.AUTOMATE_STEP_FAILED, task, download_result.error, "error")
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=download_result.error,
                started_at=started_at,
                finished_at=datetime.now(),
                download_result=download_result,
                events=events,
            )

        await self._emit(EventType.AUTOMATE_STEP_COMPLETED, task, "Automation steps complete")

        if task.parser_type.value != "none" and task.parser_instructions:
            await self._emit(EventType.PARSE_STARTED, task, "Parsing automation result")
            parse_result = await self._parser.parse(
                download_result.text,
                task.parser_instructions,
            )
            await self._emit(EventType.PARSE_COMPLETED, task, f"Parsed {len(parse_result.items)} items")
        else:
            parse_result = ParseResult(items=[])

        await self._emit(EventType.TASK_COMPLETED, task, "Automation task complete")
        return TaskResult(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            data=parse_result.items if parse_result.items else [],
            started_at=started_at,
            finished_at=datetime.now(),
            download_result=download_result,
            parse_result=parse_result,
            events=events,
        )

    async def _emit(
        self,
        event_type: EventType,
        task: Task,
        message: str = "",
        severity: str = "info",
        data: dict | None = None,
    ) -> None:
        event = Event(
            type=event_type,
            task_id=task.id,
            message=message,
            severity=severity,
            data=data or {},
        )
        await self._bus.publish(event)

    async def close(self) -> None:
        await self._downloader_selector.close()
