from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapebot.types import (
    FieldType,
    PaginationType,
    ParserType,
    ScrapeJob,
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
        self._seen: set[str] = set()

    def expand(self) -> list[Task]:
        tasks: list[Task] = []
        self._seen = set(self.job.start_urls)
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
        self._seen = set(self.job.start_urls)

        async def crawl(url: str, rule: ScrapeRule, page: int) -> None:
            max_pages = rule.pagination.max_pages or self._global_max_pages or 9999
            current_url = url
            current_page = page

            while current_url and current_page <= max_pages:
                async with sem:
                    task = self._build_task(current_url, rule, current_page)
                    task_id = await self._coordinator.submit(task)
                    result = await self._coordinator.wait_for(task_id, timeout=self.job.timeout + 10)

                if result is None:
                    return

                if result.data:
                    all_results.extend(result.data)
                    # Rule with follow_field: feed extracted URLs into other rules
                    await self._follow_results(result.data, rule)

                if not rule.pagination.enabled or current_page >= max_pages:
                    return

                next_url = self._resolve_next_url(result, rule, current_page)
                if not next_url:
                    return

                await asyncio.sleep(rule.pagination.delay)
                current_url, current_page = next_url, current_page + 1

        async with asyncio.TaskGroup() as tg:
            for url in self.job.start_urls:
                rule = self.job.rule_for_url(url)
                if rule:
                    tg.create_task(crawl(url, rule, 1))

        return all_results

    async def _follow_results(self, items: list[dict], source_rule: ScrapeRule) -> None:
        """Feed extracted URLs back into matching rules for cross-rule crawl."""
        follow_field = source_rule.follow
        if not follow_field:
            return

        discovered: list[str] = []
        for item in items:
            value = item.get(follow_field)
            if isinstance(value, list):
                discovered.extend(str(v) for v in value if v)
            elif value:
                discovered.append(str(value))

        for raw_url in discovered:
            if not raw_url.startswith("http"):
                raw_url = "https://game.ali213.net/" + raw_url.lstrip("/")

            if raw_url in self._seen:
                continue
            self._seen.add(raw_url)

            rule = self.job.rule_for_url(raw_url)
            if rule is None:
                continue
            if rule == source_rule:
                continue  # don't re-match the same list rule

            logger.info("Follow: %s → rule %s", raw_url, rule.url)
            task = self._build_task(raw_url, rule, page=1)
            tid = await self._coordinator.submit(task)
            result = await self._coordinator.wait_for(tid, timeout=self.job.timeout + 10)
            if result and result.data:
                await self._follow_results(result.data, rule)

    def _build_task(self, url: str, rule: ScrapeRule, page: int = 1) -> Task:
        return Task(
            url=url, method=rule.method,
            headers={**self.job.headers, **rule.headers},
            proxy=self.job.proxy,
            scrape_mode=rule.scrape_mode,
            downloader_type="playwright" if rule.downloader == "playwright" else "http",
            parser_type=ParserType.CSS,
            parser_instructions=self._build_instructions(rule),
            max_retries=self.job.max_retries, timeout=self.job.timeout,
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
            "selectors": css_selectors, "xpath_selectors": xpath_selectors,
            "patterns": regex_patterns, "source_map": source_map,
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
