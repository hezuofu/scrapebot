from __future__ import annotations

import pytest

from scrapebot.spider.builder import build_job_from_config
from scrapebot.types import (
    FieldSelector,
    FieldType,
    PaginationConfig,
    PaginationType,
    ScrapeJob,
    ScrapeRule,
    StorageRef,
    StorageType,
)


def test_field_selector_model():
    sel = FieldSelector(name="title", type=FieldType.CSS, selector="h1::text")
    assert sel.name == "title"
    assert sel.type == FieldType.CSS
    assert sel.multiple is False
    assert sel.required is False

    sel2 = FieldSelector(
        name="prices",
        type=FieldType.CSS,
        selector=".price::text",
        multiple=True,
        required=True,
    )
    assert sel2.multiple is True
    assert sel2.required is True


def test_regex_selector():
    sel = FieldSelector(
        name="item_id",
        type=FieldType.REGEX,
        selector=".text",
        pattern=r"#(\d+)",
    )
    assert sel.pattern == r"#(\d+)"


def test_pagination_config():
    pc = PaginationConfig(
        type=PaginationType.NEXT_LINK,
        enabled=True,
        max_pages=10,
        delay=1.0,
        next_selector="li.next a::attr(href)",
    )
    assert pc.enabled is True
    assert pc.max_pages == 10


def test_scrape_rule():
    rule = ScrapeRule(
        url="https://quotes.toscrape.com",
        method="GET",
        selectors=[
            FieldSelector(name="quote", type=FieldType.CSS, selector=".text::text", multiple=True),
            FieldSelector(name="author", type=FieldType.XPATH, selector="//small[@class='author']/text()", multiple=True),
        ],
        pagination=PaginationConfig(
            type=PaginationType.NEXT_LINK,
            enabled=True,
            max_pages=10,
            next_selector="li.next a::attr(href)",
        ),
    )
    assert len(rule.selectors) == 2
    assert rule.pagination.enabled is True


def test_build_job_from_user_config():
    data = {
        "task_id": "quotes_spider",
        "task_name": "Quotes Spider",
        "task_desc": "爬取 quotes.toscrape.com",
        "start_urls": ["https://quotes.toscrape.com"],
        "rules": [
            {
                "url": "https://quotes.toscrape.com",
                "method": "GET",
                "selectors": [
                    {"name": "quote", "type": "css", "selector": ".text::text", "multiple": True, "required": True},
                    {"name": "author", "type": "xpath", "selector": "//small[@class='author']/text()", "multiple": True},
                    {"name": "quote_id", "type": "regex", "selector": ".text", "pattern": r"#(\d+)", "required": False},
                ],
                "pagination_type": "next_link",
                "pagination_enabled": True,
                "pagination_max_pages": 10,
                "pagination_delay": 1,
                "pagination_next_selector": "li.next a::attr(href)",
            }
        ],
        "concurrency": 2,
        "download_delay": 1,
        "storage": {"type": "file", "file": {"output_dir": "output", "format": "json"}},
    }

    job = build_job_from_config(data)
    assert isinstance(job, ScrapeJob)
    assert job.job_id == "quotes_spider"
    assert job.name == "Quotes Spider"
    assert len(job.start_urls) == 1
    assert len(job.rules) == 1
    assert len(job.rules[0].selectors) == 3
    assert job.rules[0].selectors[0].type == FieldType.CSS
    assert job.rules[0].selectors[1].type == FieldType.XPATH
    assert job.rules[0].selectors[2].type == FieldType.REGEX
    assert job.rules[0].pagination.enabled is True
    assert job.rules[0].pagination.type == PaginationType.NEXT_LINK
    assert job.concurrency == 2
    assert job.storage is not None
    assert job.storage.type == StorageType.FILE
    assert job.storage.file == {"output_dir": "output", "format": "json"}


def test_selectors_for_url():
    job = ScrapeJob(
        job_id="test",
        name="Test",
        start_urls=["https://example.com"],
        rules=[
            ScrapeRule(
                url="https://example.com",
                selectors=[FieldSelector(name="title", type=FieldType.CSS, selector="h1")],
            )
        ],
    )
    sels = job.selectors_for_url("https://example.com")
    assert len(sels) == 1
    assert sels[0].name == "title"

    # No match
    sels = job.selectors_for_url("https://other.com")
    assert len(sels) == 0


def test_model_dump_roundtrip():
    """Verify ScrapeJob can serialize and deserialize."""
    job = ScrapeJob(
        job_id="test_job",
        name="Test",
        start_urls=["https://example.com"],
        rules=[ScrapeRule(url="https://example.com")],
    )
    data = job.model_dump()
    restored = ScrapeJob(**data)
    assert restored.job_id == "test_job"
    assert len(restored.rules) == 1
