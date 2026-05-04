from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from scrapebot.exceptions import DownloadError
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
        self._pool_size = max(1, pool_size)
        self._browser_type = browser_type
        self._browser = None
        self._playwright = None
        self._contexts: asyncio.Queue = asyncio.Queue()
        self._pool_lock = asyncio.Lock()
        self._inflight = 0

    async def _ensure_browser(self) -> None:
        if self._playwright is None:
            from playwright.async_api import async_playwright

            try:
                pw = await async_playwright().start()
                self._playwright = pw
                browser_launcher = getattr(pw, self._browser_type)
                self._browser = await browser_launcher.launch(headless=self._headless)
            except Exception:
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                raise DownloadError(f"Failed to launch {self._browser_type} browser")

    async def _get_context(self, proxy: str | None = None, headers: dict[str, str] | None = None):
        await self._ensure_browser()

        # Check pool first
        try:
            ctx = self._contexts.get_nowait()
            self._inflight += 1
            return ctx
        except asyncio.QueueEmpty:
            pass

        async with self._pool_lock:
            if self._inflight < self._pool_size:
                self._inflight += 1
                context_opts: dict = {}
                if proxy:
                    context_opts["proxy"] = {"server": proxy}
                if headers:
                    context_opts["extra_http_headers"] = headers
                return await self._browser.new_context(**context_opts)

        # Pool full, wait for one to return
        ctx = await self._contexts.get()
        self._inflight += 1
        return ctx

    def _return_context(self, ctx) -> None:
        self._inflight -= 1
        try:
            self._contexts.put_nowait(ctx)
        except asyncio.QueueFull:
            pass  # pool has enough contexts

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
        steps: list[dict[str, Any]] | None = None,
    ) -> DownloadResult:
        # For per-request proxy/headers, create a fresh context
        needs_fresh = bool(proxy) or bool(headers)
        fresh_context = None
        reused = False

        start = time.monotonic()
        try:
            if needs_fresh:
                await self._ensure_browser()
                ctx_opts: dict = {}
                if proxy:
                    ctx_opts["proxy"] = {"server": proxy}
                if headers:
                    ctx_opts["extra_http_headers"] = headers
                context = await self._browser.new_context(**ctx_opts)
                fresh_context = context
            else:
                context = await self._get_context()
                reused = True

            page = await context.new_page()
            try:
                resp = await page.goto(url, timeout=timeout * 1000)
                status_code = resp.status if resp else 0
                content = await page.content()
                elapsed = (time.monotonic() - start) * 1000
                resp_headers = dict(resp.headers) if resp else {}
                return DownloadResult(
                    url=page.url,
                    status_code=status_code,
                    content=content.encode(),
                    text=content,
                    headers=resp_headers,
                    elapsed_ms=round(elapsed, 2),
                )
            finally:
                await page.close()
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return DownloadResult(url=url, elapsed_ms=round(elapsed, 2), error=str(exc))
        finally:
            if fresh_context:
                await fresh_context.close()
            elif reused:
                self._return_context(context)

    async def close(self) -> None:
        while not self._contexts.empty():
            try:
                ctx = self._contexts.get_nowait()
                await ctx.close()
            except asyncio.QueueEmpty:
                break
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
            self._browser = None
            self._playwright = None
