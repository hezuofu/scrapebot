from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client
        self._baselines: dict[str, str] = {}

    def set_baseline(self, url_pattern: str, html_sample: str) -> None:
        self._baselines[url_pattern] = html_sample

    async def detect(
        self,
        html: str,
        url_pattern: str | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []

        if self._is_empty_or_error(html):
            issues.append("Page appears empty or error page")

        if self._is_access_denied(html):
            issues.append("Access denied or blocked")

        if url_pattern and url_pattern in self._baselines:
            baseline_issue = await self._compare_with_baseline(
                html,
                self._baselines[url_pattern],
            )
            if baseline_issue:
                issues.append(baseline_issue)

        return {
            "is_anomalous": len(issues) > 0,
            "issues": issues,
        }

    def _is_empty_or_error(self, html: str) -> bool:
        stripped = html.strip()
        return len(stripped) < 100 or "error" in stripped[:200].lower()

    def _is_access_denied(self, html: str) -> bool:
        lower = html[:500].lower()
        return any(
            kw in lower
            for kw in ["access denied", "403 forbidden", "blocked", "captcha"]
        )

    async def _compare_with_baseline(self, current: str, baseline: str) -> str | None:
        if self._llm is None:
            return None

        try:
            result = await self._llm.extract(
                f"Compare these HTML structures. Has the page changed significantly?",
                f"Baseline:\n{baseline[:1000]}\n\nCurrent:\n{current[:1000]}",
            )
            answer = str(result[0].get("result", "") if result else "").lower()
            if answer.startswith("yes"):
                return "Page structure has changed significantly from baseline"
            return None
        except Exception:
            return None
