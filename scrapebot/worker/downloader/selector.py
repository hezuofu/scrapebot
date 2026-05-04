from __future__ import annotations

import logging
from fnmatch import fnmatch

from scrapebot.types import DownloaderType, ScrapeMode, Task
from scrapebot.worker.downloader.base import BaseDownloader
from scrapebot.worker.downloader.browser_automator import BrowserAutomator
from scrapebot.worker.downloader.http_downloader import HTTPDownloader
from scrapebot.worker.downloader.playwright_downloader import PlaywrightDownloader

logger = logging.getLogger(__name__)


class DownloaderSelector:
    def __init__(
        self,
        http_downloader: BaseDownloader | None = None,
        playwright_downloader: BaseDownloader | None = None,
        browser_automator: BrowserAutomator | None = None,
        site_rules: dict | None = None,
        enable_fallback: bool = True,
    ) -> None:
        self._http = http_downloader or HTTPDownloader()
        self._playwright = playwright_downloader or PlaywrightDownloader()
        self._automator = browser_automator or BrowserAutomator()
        self._site_rules = site_rules or {}
        self._enable_fallback = enable_fallback
        self._fallback_domains: set[str] = set()

    def select_downloader(self, task: Task) -> BaseDownloader:
        override = self._site_override(task.url)

        if override == "playwright":
            return self._playwright
        if override == "http":
            return self._http

        # Remembered fallback: this domain previously needed JS
        domain = self._domain_for(task.url)
        if self._enable_fallback and domain in self._fallback_domains:
            logger.info("Fallback to Playwright for %s (remembered)", domain)
            return self._playwright

        if task.scrape_mode == ScrapeMode.RENDER or task.downloader_type == DownloaderType.PLAYWRIGHT:
            return self._playwright
        return self._http

    async def report_result(self, task: Task, result) -> None:
        """After task completes, analyze result to refine future selections."""
        if not self._enable_fallback:
            return
        dl = getattr(result, "download_result", None) or result
        if dl is None:
            return
        # Fallback trigger: page is empty or looks like it needs JS
        text = getattr(dl, "text", "") or ""
        if self._needs_js(text, dl):
            domain = self._domain_for(task.url)
            self._fallback_domains.add(domain)
            logger.info("Domain %s added to Playwright fallback list", domain)

    @staticmethod
    def _needs_js(text: str, dl) -> bool:
        if not text or len(text.strip()) < 200:
            return True
        indicators = [
            "You need to enable JavaScript",
            "Please enable JavaScript",
            "noscript",
            "<body></body>",
            '<div id="app"></div>',
            '<div id="root"></div>',
        ]
        lower = text[:500].lower()
        return any(ind.lower() in lower for ind in indicators)

    def select_automator(self) -> BrowserAutomator:
        return self._automator

    def _site_override(self, url: str) -> str | None:
        for rule in self._site_rules.get("sites", []):
            pattern = rule.get("pattern", "")
            if fnmatch(url, pattern):
                dl = rule.get("downloader")
                if dl:
                    return dl
                mode = rule.get("scrape_mode", "")
                if mode == "render":
                    return "playwright"
                if mode == "fetch":
                    return "http"
                return mode or None
        return None

    @staticmethod
    def _domain_for(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return url

    async def close(self) -> None:
        await self._http.close()
        await self._playwright.close()
        await self._automator.close()
