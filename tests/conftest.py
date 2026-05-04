from __future__ import annotations

import pytest

from scrapebot.config.settings import Settings
from scrapebot.types import Task


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def sample_task() -> Task:
    return Task(
        url="https://example.com",
        parser_instructions={
            "selectors": {
                "title": "h1",
                "description": "p",
            }
        },
    )


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p class="description">This is a test paragraph.</p>
    <ul class="items">
        <li class="item">
            <span class="name">Item 1</span>
            <span class="price">$10.00</span>
        </li>
        <li class="item">
            <span class="name">Item 2</span>
            <span class="price">$20.00</span>
        </li>
    </ul>
</body>
</html>"""
