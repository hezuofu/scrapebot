"""Convert user-facing dict config into validated ScrapeJob model."""

from __future__ import annotations

from typing import Any

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


def build_job_from_config(data: dict[str, Any]) -> ScrapeJob:
    """Parse a user-facing config dict into a ScrapeJob with full validation.

    Handles both the new structured format and provides defaults for
    missing fields.
    """
    rules: list[ScrapeRule] = []
    for rule_data in data.get("rules", []):
        selectors: list[FieldSelector] = []
        for sel_data in rule_data.get("selectors", []):
            selectors.append(FieldSelector(
                name=sel_data["name"],
                description=sel_data.get("description", ""),
                type=FieldType(sel_data.get("type", "css")),
                selector=sel_data.get("selector", ""),
                pattern=sel_data.get("pattern"),
                multiple=sel_data.get("multiple", False),
                required=sel_data.get("required", False),
                attribute=sel_data.get("attribute"),
            ))

        pagination = PaginationConfig(
            type=PaginationType(rule_data.get("pagination_type", "none")),
            enabled=rule_data.get("pagination_enabled", False),
            max_pages=rule_data.get("pagination_max_pages", 0),
            delay=rule_data.get("pagination_delay", 1.0),
            next_selector=rule_data.get("pagination_next_selector"),
            page_param=rule_data.get("pagination_page_param"),
        )

        rules.append(ScrapeRule(
            url=rule_data["url"],
            method=rule_data.get("method", "GET"),
            selectors=selectors,
            pagination=pagination,
            downloader=rule_data.get("downloader", "http"),
            scrape_mode=rule_data.get("scrape_mode", "fetch"),
            headers=rule_data.get("headers", {}),
            before_script=rule_data.get("before_script"),
            follow=rule_data.get("follow"),
        ))

    storage = None
    if "storage" in data:
        st = data["storage"]
        storage = StorageRef(
            type=StorageType(st.get("type", "file")),
            file=st.get("file"),
            postgres=st.get("postgres"),
            mongodb=st.get("mongodb"),
            s3=st.get("s3"),
            kafka=st.get("kafka"),
        )

    return ScrapeJob(
        job_id=data.get("task_id") or data.get("job_id", ""),
        name=data.get("task_name") or data.get("name", ""),
        description=data.get("task_desc") or data.get("description", ""),
        start_urls=data.get("start_urls", []),
        rules=rules,
        concurrency=data.get("concurrency", 1),
        download_delay=data.get("download_delay", 1.0),
        max_retries=data.get("max_retries", 3),
        timeout=data.get("timeout", 30.0),
        headers=data.get("headers", {}),
        proxy=data.get("proxy"),
        storage=storage,
    )
