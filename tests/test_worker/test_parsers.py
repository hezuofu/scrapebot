from __future__ import annotations

import pytest

from scrapebot.worker.parser.css_parser import CSSParser
from scrapebot.worker.parser.xpath_parser import XPathParser
from scrapebot.worker.parser.regex_parser import RegexParser
from scrapebot.worker.parser.composite_parser import CompositeParser


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p class="desc">This is a description.</p>
    <ul>
        <li class="item"><span class="name">Item A</span><span class="price">$10</span></li>
        <li class="item"><span class="name">Item B</span><span class="price">$20</span></li>
    </ul>
</body>
</html>"""


@pytest.mark.asyncio
async def test_css_single_item():
    parser = CSSParser()
    result = await parser.parse(SAMPLE_HTML, {
        "selectors": {"title": "h1", "desc": "p.desc"},
    })
    assert len(result.items) == 1
    assert result.items[0]["title"] == "Hello World"
    assert result.items[0]["desc"] == "This is a description."


@pytest.mark.asyncio
async def test_css_no_selectors():
    parser = CSSParser()
    result = await parser.parse(SAMPLE_HTML, {})
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_xpath_parser():
    parser = XPathParser()
    result = await parser.parse(SAMPLE_HTML, {
        "selectors": {"title": "//h1/text()"},
    })
    assert len(result.items) == 1
    assert result.items[0]["title"] == "Hello World"


@pytest.mark.asyncio
async def test_regex_parser():
    parser = RegexParser()
    result = await parser.parse(SAMPLE_HTML, {
        "patterns": {"title": r"<h1>(.*?)</h1>"},
    })
    assert result.items[0]["title"] == "Hello World"


@pytest.mark.asyncio
async def test_regex_no_match():
    parser = RegexParser()
    result = await parser.parse(SAMPLE_HTML, {
        "patterns": {"missing": r"<nope>(.*?)</nope>"},
    })
    assert result.items[0]["missing"] is None


@pytest.mark.asyncio
async def test_composite_first_strategy_wins():
    parser = CompositeParser()
    result = await parser.parse(SAMPLE_HTML, {
        "strategies": ["css", "xpath"],
        "selectors": {"title": "h1"},
    })
    assert len(result.items) == 1
    assert result.items[0]["title"] == "Hello World"
