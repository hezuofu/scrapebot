from __future__ import annotations

import time

from scrapebot.types import DownloadResult
from scrapebot.worker.downloader.base import BaseDownloader


class PlaywrightDownloader(BaseDownloader):
    def __init__(
        self,
        headless: bool = True,
        pool_size: int = 3,
        browser_type: str = "chromium",
    ) -> None:
        self._headless = headless
        self._pool_size = pool_size
        self._browser_type = browser_type
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self) -> None:
        if self._playwright is None:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            self._playwright = pw
            browser_launcher = getattr(pw, self._browser_type)
            self._browser = await browser_launcher.launch(headless=self._headless)

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> DownloadResult:
        await self._ensure_browser()
        start = time.monotonic()

        context_opts: dict = {}
        if proxy:
            context_opts["proxy"] = {"server": proxy}
        if headers:
            context_opts["extra_http_headers"] = headers

        context = await self._browser.new_context(**context_opts)
        try:
            page = await context.new_page()
            resp = await page.goto(url, timeout=timeout * 1000)
            status_code = resp.status if resp else 0
            content = await page.content()
            elapsed = (time.monotonic() - start) * 1000

            resp_headers: dict[str, str] = {}
            if resp:
                resp_headers = dict(resp.headers)

            return DownloadResult(
                url=page.url,
                status_code=status_code,
                content=content.encode(),
                text=content,
                headers=resp_headers,
                elapsed_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return DownloadResult(
                url=url,
                elapsed_ms=round(elapsed, 2),
                error=str(exc),
            )
        finally:
            await context.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
            self._browser = None
            self._playwright = None
