from __future__ import annotations

import pytest

from scrapebot.spider.runner import SpiderRunner
from scrapebot.types import (
    FieldSelector,
    FieldType,
    PaginationConfig,
    PaginationType,
    ScrapeJob,
    ScrapeRule,
    Task,
)


@pytest.fixture
def quotes_job() -> ScrapeJob:
    return ScrapeJob(
        job_id="quotes_spider",
        name="Quotes Spider",
        start_urls=["https://quotes.toscrape.com"],
        concurrency=1,
        download_delay=0.5,
        rules=[
            ScrapeRule(
                url="https://quotes.toscrape.com",
                method="GET",
                selectors=[
                    FieldSelector(name="quote", type=FieldType.CSS, selector=".text::text", multiple=True),
                    FieldSelector(name="author", type=FieldType.XPATH, selector="//small[@class='author']/text()", multiple=True),
                    FieldSelector(name="tags", type=FieldType.CSS, selector=".tags .tag::text", multiple=True),
                ],
                pagination=PaginationConfig(
                    type=PaginationType.NEXT_LINK,
                    enabled=True,
                    max_pages=3,
                    delay=0.1,
                    next_selector="li.next a",
                ),
            )
        ],
    )


def test_expand_generates_tasks(quotes_job):
    runner = SpiderRunner(quotes_job)
    tasks = runner.expand()
    assert len(tasks) == 1
    task = tasks[0]
    assert isinstance(task, Task)
    assert task.url == "https://quotes.toscrape.com"
    assert task.metadata.get("job_id") == "quotes_spider"
    assert task.metadata.get("page") == 1
    assert task.max_retries == 3
    assert task.timeout == 30.0


def test_build_instructions_css(quotes_job):
    runner = SpiderRunner(quotes_job)
    instructions = runner._build_instructions(quotes_job.rules[0])
    assert "selectors" in instructions
    assert instructions["selectors"]["quote"] == ".text::text"
    assert instructions["extract_list"] is True  # multiple=True fields exist


def test_build_instructions_xpath(quotes_job):
    runner = SpiderRunner(quotes_job)
    instructions = runner._build_instructions(quotes_job.rules[0])
    assert "xpath_selectors" in instructions
    assert instructions["xpath_selectors"]["author"] == "//small[@class='author']/text()"


def test_expand_multiple_start_urls():
    job = ScrapeJob(
        job_id="multi",
        name="Multi",
        start_urls=["https://a.com", "https://b.com"],
        rules=[ScrapeRule(url="https://a.com"), ScrapeRule(url="https://b.com")],
    )
    runner = SpiderRunner(job)
    tasks = runner.expand()
    assert len(tasks) == 2


def test_no_rule_match_skips_url():
    job = ScrapeJob(
        job_id="skip",
        name="Skip",
        start_urls=["https://unmatched.com"],
        rules=[ScrapeRule(url="https://matched.com")],
    )
    runner = SpiderRunner(job)
    tasks = runner.expand()
    assert len(tasks) == 0


def test_build_page_url():
    rule = ScrapeRule(
        url="https://example.com/list",
        pagination=PaginationConfig(type=PaginationType.PAGE_NUMBER, enabled=True, page_param="p"),
    )
    next_url = SpiderRunner._resolve_next_url(None, rule, 2)
    assert next_url == "https://example.com/list?p=3"


def test_task_inherits_job_settings():
    job = ScrapeJob(
        job_id="settings_test",
        name="Settings",
        start_urls=["https://example.com"],
        rules=[ScrapeRule(url="https://example.com")],
        max_retries=5,
        timeout=60.0,
        headers={"Authorization": "Bearer xyz"},
        proxy="http://proxy:8080",
    )
    runner = SpiderRunner(job)
    tasks = runner.expand()
    task = tasks[0]
    assert task.max_retries == 5
    assert task.timeout == 60.0
    assert task.headers["Authorization"] == "Bearer xyz"
    assert task.proxy == "http://proxy:8080"
