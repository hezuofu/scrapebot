from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapebot.types import (
    FieldSelector,
    FieldType,
    PaginationType,
    ParserType,
    ScrapeJob,
    ScrapeMode,
    ScrapeRule,
    Task,
)

logger = logging.getLogger(__name__)


class SpiderRunner:
    def __init__(
        self,
        job: ScrapeJob,
        coordinator=None,
        delay: float | None = None,
        max_pages: int | None = None,
    ) -> None:
        self.job = job
        self._coordinator = coordinator
        self._delay = delay if delay is not None else job.download_delay
        self._global_max_pages = max_pages or 0

    def expand(self) -> list[Task]:
        tasks: list[Task] = []
        for url in self.job.start_urls:
            rule = self.job.rule_for_url(url)
            if rule is None:
                logger.warning("No rule matches URL: %s", url)
                continue
            tasks.append(self._build_task(url, rule, page=1))
        return tasks

    async def run(self) -> list[dict]:
        if self._coordinator is None:
            raise RuntimeError("SpiderRunner.run() requires a coordinator")

        all_results: list[dict] = []
        sem = asyncio.Semaphore(self.job.concurrency)

        async def crawl_page(url: str, rule: ScrapeRule, page: int) -> None:
            max_pages = rule.pagination.max_pages or self._global_max_pages or 9999

            while url and page <= max_pages:
                async with sem:
                    task = self._build_task(url, rule, page)
                    task_id = await self._coordinator.submit(task)
                    result = await self._coordinator.wait_for(task_id, timeout=self.job.timeout + 10)

                if result is None:
                    return

                if result.data:
                    all_results.extend(result.data)

                if not rule.pagination.enabled or page >= max_pages:
                    return

                next_url = self._resolve_next_url(result, rule, page)
                if not next_url:
                    return

                await asyncio.sleep(rule.pagination.delay)
                url, page = next_url, page + 1

        async with asyncio.TaskGroup() as tg:
            for url in self.job.start_urls:
                rule = self.job.rule_for_url(url)
                if rule:
                    tg.create_task(crawl_page(url, rule, 1))

        return all_results

    def _build_task(self, url: str, rule: ScrapeRule, page: int = 1) -> Task:
        return Task(
            url=url,
            method=rule.method,
            headers={**self.job.headers, **rule.headers},
            proxy=self.job.proxy,
            scrape_mode=rule.scrape_mode,
            downloader_type="playwright" if rule.downloader == "playwright" else "http",
            parser_type=ParserType.CSS,
            parser_instructions=self._build_instructions(rule),
            max_retries=self.job.max_retries,
            timeout=self.job.timeout,
            metadata={"job_id": self.job.job_id, "rule_url": rule.url, "page": page},
        )

    @staticmethod
    def _build_instructions(rule: ScrapeRule) -> dict:
        css_selectors: dict[str, str] = {}
        xpath_selectors: dict[str, str] = {}
        regex_patterns: dict[str, str] = {}
        attributes: dict[str, str] = {}
        source_map: dict[str, str] = {}

        for sel in rule.selectors:
            if sel.type == FieldType.CSS:
                css_selectors[sel.name] = sel.selector
            elif sel.type == FieldType.XPATH:
                xpath_selectors[sel.name] = sel.selector
            elif sel.type == FieldType.REGEX:
                regex_patterns[sel.name] = sel.pattern or ""
                source_map[sel.name] = sel.selector
            if sel.attribute:
                attributes[sel.name] = sel.attribute

        return {
            "selectors": css_selectors,
            "xpath_selectors": xpath_selectors,
            "patterns": regex_patterns,
            "source_map": source_map,
            "attributes": attributes,
            "extract_list": any(s.multiple for s in rule.selectors),
            "list_selector": "body",
            "required_fields": [s.name for s in rule.selectors if s.required],
            "field_meta": {s.name: {"description": s.description, "multiple": s.multiple}
                           for s in rule.selectors},
        }

    @staticmethod
    def _resolve_next_url(result, rule: ScrapeRule, current_page: int) -> str | None:
        pagination = rule.pagination
        if pagination.type == PaginationType.NEXT_LINK:
            if result is None:
                return None
            return SpiderRunner._extract_next_link(result, pagination.next_selector)
        elif pagination.type == PaginationType.PAGE_NUMBER:
            param = pagination.page_param or "page"
            sep = "&" if "?" in rule.url else "?"
            return f"{rule.url}{sep}{param}={current_page + 1}"
        return None

    @staticmethod
    def _extract_next_link(result, next_selector: str | None) -> str | None:
        if not next_selector or not result.download_result:
            return None
        text = result.download_result.text
        if not text:
            return None
        soup = BeautifulSoup(text, "lxml")
        el = soup.select_one(next_selector)
        if el and el.get("href"):
            return urljoin(result.download_result.url, el["href"])
        return None
