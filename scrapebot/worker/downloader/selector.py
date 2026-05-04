from __future__ import annotations

from fnmatch import fnmatch

from scrapebot.types import DownloaderType, ScrapeMode, Task
from scrapebot.worker.downloader.base import BaseDownloader
from scrapebot.worker.downloader.browser_automator import BrowserAutomator
from scrapebot.worker.downloader.http_downloader import HTTPDownloader
from scrapebot.worker.downloader.playwright_downloader import PlaywrightDownloader


class DownloaderSelector:
    """Routes tasks to the correct downloader or automator based on mode and site rules.

    Two distinct return types by design — downloaders and automators have
    different interfaces, so the caller must know which it needs.
    """

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

    def select_downloader(self, task: Task) -> BaseDownloader:
        """Return the appropriate downloader for fetch/render modes."""
        override = self._site_override(task.url)
        if override == "playwright":
            return self._playwright
        if override == "http":
            return self._http

        if task.scrape_mode == ScrapeMode.RENDER or task.downloader_type == DownloaderType.PLAYWRIGHT:
            return self._playwright
        return self._http

    def select_automator(self) -> BrowserAutomator:
        """Return the browser automator instance."""
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

    async def close(self) -> None:
        await self._http.close()
        await self._playwright.close()
        await self._automator.close()
