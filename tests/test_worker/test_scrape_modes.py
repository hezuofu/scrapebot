from __future__ import annotations

import pytest

from scrapebot.types import ScrapeMode, Task
from scrapebot.worker.downloader.selector import DownloaderSelector
from scrapebot.worker.downloader.http_downloader import HTTPDownloader
from scrapebot.worker.downloader.playwright_downloader import PlaywrightDownloader
from scrapebot.worker.downloader.browser_automator import BrowserAutomator


def test_fetch_mode_selects_http_downloader():
    selector = DownloaderSelector()
    task = Task(url="http://example.com", scrape_mode=ScrapeMode.FETCH)
    downloader = selector.select_downloader(task)
    assert isinstance(downloader, HTTPDownloader)


def test_render_mode_selects_playwright():
    selector = DownloaderSelector()
    task = Task(url="http://example.com", scrape_mode=ScrapeMode.RENDER)
    downloader = selector.select_downloader(task)
    assert isinstance(downloader, PlaywrightDownloader)


def test_automate_mode_uses_automator():
    selector = DownloaderSelector()
    automator = selector.select_automator()
    assert isinstance(automator, BrowserAutomator)


def test_site_rules_override_mode():
    rules = {
        "sites": [
            {"pattern": "*.spa.io/*", "scrape_mode": "render"},
        ]
    }
    selector = DownloaderSelector(site_rules=rules)
    task = Task(url="http://app.spa.io/page", scrape_mode=ScrapeMode.FETCH)
    downloader = selector.select_downloader(task)
    assert isinstance(downloader, PlaywrightDownloader)


def test_scrape_mode_values():
    assert ScrapeMode.FETCH.value == "fetch"
    assert ScrapeMode.RENDER.value == "render"
    assert ScrapeMode.AUTOMATE.value == "automate"


def test_task_defaults_to_fetch():
    task = Task(url="http://example.com")
    assert task.scrape_mode == ScrapeMode.FETCH
    assert task.automate_steps == []


def test_task_with_automate_steps():
    task = Task(
        url="http://example.com",
        scrape_mode=ScrapeMode.AUTOMATE,
        automate_steps=[
            {"action": "navigate", "url": "http://example.com/login"},
            {"action": "type", "selector": "#username", "value": "user"},
            {"action": "click", "selector": "#submit"},
        ],
    )
    assert len(task.automate_steps) == 3
    assert task.automate_steps[0]["action"] == "navigate"
