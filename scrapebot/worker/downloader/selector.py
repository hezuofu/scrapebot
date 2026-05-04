from __future__ import annotations

from fnmatch import fnmatch

from scrapebot.types import DownloaderType, ScrapeMode, Task
from scrapebot.worker.downloader.base import BaseDownloader
from scrapebot.worker.downloader.browser_automator import BrowserAutomator
from scrapebot.worker.downloader.http_downloader import HTTPDownloader
from scrapebot.worker.downloader.playwright_downloader import PlaywrightDownloader


class DownloaderSelector:
    def __init__(
        self,
        http_downloader: BaseDownloader | None = None,
        playwright_downloader: BaseDownloader | None = None,
        browser_automator: BrowserAutomator | None = None,
        site_rules: dict | None = None,
    ) -> None:
        self._http = http_downloader or HTTPDownloader()
        self._playwright = playwright_downloader or PlaywrightDownloader()
        self._automator = browser_automator or BrowserAutomator()
        self._site_rules = site_rules or {}

    def select(self, task: Task) -> BaseDownloader:
        """Select downloader based on scrape mode and site rules."""
        rules = self._site_rules.get("sites", [])
        for rule in rules:
            pattern = rule.get("pattern", "")
            if fnmatch(task.url, pattern):
                if "scrape_mode" in rule:
                    return self._select_by_mode(ScrapeMode(rule["scrape_mode"]))
                dl_type = rule.get("downloader", "http")
                return self._playwright if dl_type == "playwright" else self._http

        return self._select_by_mode(task.scrape_mode)

    def _select_by_mode(self, mode: ScrapeMode) -> BaseDownloader:
        if mode == ScrapeMode.AUTOMATE:
            return self._automator
        elif mode == ScrapeMode.RENDER:
            return self._playwright
        else:
            return self._http

    def get_automator(self) -> BrowserAutomator:
        return self._automator

    async def close(self) -> None:
        await self._http.close()
        await self._playwright.close()
        await self._automator.close()
