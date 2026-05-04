from __future__ import annotations

import asyncio
import time
from typing import Any

from scrapebot.events.bus import EventBus
from scrapebot.types import DownloadResult
from scrapebot.worker.downloader.base import BaseDownloader


class BrowserAutomator(BaseDownloader):
    SUPPORTED_ACTIONS = {
        "navigate", "click", "type", "scroll", "wait",
        "wait_for_selector", "wait_for_navigation",
        "select", "hover", "press", "screenshot",
        "extract", "extract_all", "evaluate", "fill_form",
    }

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",
        viewport: dict[str, int] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._headless = headless
        self._browser_type = browser_type
        self._viewport = viewport or {"width": 1920, "height": 1080}
        self._browser = None
        self._playwright = None
        self._bus = event_bus
        self._steps: list[dict[str, Any]] = []

    async def _ensure_browser(self) -> None:
        if self._playwright is None:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self._playwright = pw
            try:
                browser_launcher = getattr(pw, self._browser_type)
                self._browser = await browser_launcher.launch(headless=self._headless)
            except Exception:
                await pw.stop()
                self._playwright = None
                raise

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 60.0,
        steps: list[dict[str, Any]] | None = None,
    ) -> DownloadResult:
        await self._ensure_browser()

        context_opts: dict[str, Any] = {"viewport": self._viewport}
        if proxy:
            context_opts["proxy"] = {"server": proxy}
        if headers:
            context_opts["extra_http_headers"] = headers

        context = await self._browser.new_context(**context_opts)
        page = await context.new_page()
        start_time = time.monotonic()
        _steps = steps or []

        try:
            await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")

            for step in _steps:
                await self._execute_step(page, step, timeout)

            elapsed = (time.monotonic() - start_time) * 1000
            content = await page.content()

            return DownloadResult(
                url=page.url,
                status_code=200,
                text=content,
                content=content.encode(),
                elapsed_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            return DownloadResult(url=url, elapsed_ms=round(elapsed, 2), error=str(exc))
        finally:
            await context.close()

    async def _execute_step(self, page: Any, step: dict[str, Any], timeout: float) -> None:
        action = step.get("action", "")
        selector = step.get("selector", "")
        value = step.get("value")
        options = step.get("options", {})

        if action not in self.SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported action: {action}")

        if action == "navigate":
            await page.goto(step["url"], timeout=timeout * 1000,
                            wait_until=step.get("wait_until", "domcontentloaded"))
        elif action == "click":
            await page.wait_for_selector(selector, timeout=timeout * 1000)
            await page.click(selector, **options)
        elif action == "type":
            await page.wait_for_selector(selector, timeout=timeout * 1000)
            await page.fill(selector, str(value) if value else "", **options)
        elif action == "scroll":
            if value:
                await page.evaluate(f"window.scrollBy(0, {value})")
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif action == "wait":
            await asyncio.sleep(float(value or 1.0))
        elif action == "wait_for_selector":
            await page.wait_for_selector(selector, timeout=(float(value) if value else timeout) * 1000, **options)
        elif action == "wait_for_navigation":
            await page.wait_for_load_state(value or "networkidle", **options)
        elif action == "select":
            await page.select_option(selector, value, **options)
        elif action == "hover":
            await page.hover(selector, **options)
        elif action == "press":
            await page.press(selector, str(value) if value else "Enter", **options)
        elif action == "screenshot":
            await page.screenshot(
                path=step.get("path", f"screenshot_{int(time.time())}.png"),
                full_page=step.get("full_page", True))
        elif action == "evaluate":
            step["_result"] = await page.evaluate(str(value))
        elif action == "extract":
            step["_result"] = await self._extract(page, step.get("instructions", {}))
        elif action == "extract_all":
            step["_result"] = await self._extract(page, step.get("instructions", {}))
        elif action == "fill_form":
            fields = step.get("fields", {})
            for field_selector, field_value in fields.items():
                await page.fill(field_selector, str(field_value))
            submit_selector = step.get("submit_selector")
            if submit_selector:
                await page.click(submit_selector)

    async def _extract(self, page: Any, instructions: dict[str, Any]) -> list[dict[str, Any]]:
        selectors = instructions.get("selectors", {})
        extract_list = instructions.get("extract_list", False)
        list_selector = instructions.get("list_selector", "body")

        if extract_list:
            items = []
            elements = await page.query_selector_all(list_selector)
            for el in elements:
                item: dict[str, Any] = {}
                for field, css in selectors.items():
                    try:
                        child = await el.query_selector(css.lstrip("& "))
                        if child:
                            attr = (instructions.get("attributes", {}) or {}).get(field)
                            item[field] = await child.get_attribute(attr) if attr else await child.inner_text()
                        else:
                            item[field] = None
                    except Exception:
                        item[field] = None
                items.append(item)
            return items
        else:
            item: dict[str, Any] = {}
            for field, css in selectors.items():
                try:
                    el = await page.query_selector(css)
                    if el:
                        attr = (instructions.get("attributes", {}) or {}).get(field)
                        item[field] = await el.get_attribute(attr) if attr else await el.inner_text()
                    else:
                        item[field] = None
                except Exception:
                    item[field] = None
            return [item]

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
            self._browser = None
            self._playwright = None
