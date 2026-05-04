from __future__ import annotations

import pytest

from scrapebot.pipeline.cleaning.field_cleaner import FieldCleaner
from scrapebot.pipeline.cleaning.html_cleaner import HTMLCleaner
from scrapebot.pipeline.cleaning.validator import DataValidator
from scrapebot.pipeline.transformer import DataTransformer
from scrapebot.pipeline.deduplication.bloom_filter import BloomFilter
from scrapebot.pipeline.deduplication.lru_dedup import LRUDedup


@pytest.mark.asyncio
async def test_field_cleaner_strips_whitespace():
    cleaner = FieldCleaner()
    data = [{"name": "  hello  world  ", "age": " 42 "}]
    result = await cleaner.process(data)
    assert result[0]["name"] == "hello world"
    assert result[0]["age"] == "42"


@pytest.mark.asyncio
async def test_html_cleaner():
    cleaner = HTMLCleaner()
    result = cleaner.clean("<p>Hello <b>World</b></p>")
    assert "Hello" in result
    assert "World" in result
    assert "<b>" not in result


@pytest.mark.asyncio
async def test_validator_filters_empty():
    validator = DataValidator()
    data = [{"a": "ok"}, {}, {"b": None}, {"c": ""}, {"d": "valid"}]
    result = await validator.process(data)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_transformer_mapping():
    transformer = DataTransformer(mapping={"old_name": "new_name"})
    data = [{"old_name": "value", "other": "keep"}]
    result = await transformer.process(data)
    assert result[0]["new_name"] == "value"
    assert "old_name" not in result[0]


def test_bloom_filter_add_and_check():
    bf = BloomFilter(capacity=1000)
    assert bf.add_if_new("hello")
    assert not bf.add_if_new("hello")
    assert bf.add_if_new("world")


def test_lru_dedup():
    dedup = LRUDedup(max_size=100)
    assert not dedup.is_duplicate("item1")
    assert dedup.is_duplicate("item1")
    assert not dedup.is_duplicate("item2")
