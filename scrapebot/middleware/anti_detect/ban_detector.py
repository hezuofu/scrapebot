from __future__ import annotations

import re

from scrapebot.types import DownloadResult


class BanDetector:
    _PATTERN = re.compile(
        r"access denied|ip.*blocked|has been blocked|"
        r"your request has been blocked|too many requests|"
        r"rate limit exceeded|request denied|"
        r"you have been blocked|unauthorized access",
        re.IGNORECASE,
    )

    def __init__(self, trigger: object = None) -> None:
        self._trigger = trigger

    def detect(self, result: DownloadResult) -> bool:
        if result.status_code in (403, 401, 429):
            return True
        return bool(self._PATTERN.search(result.text))

    def identify_reason(self, result: DownloadResult) -> str | None:
        lower = result.text.lower()
        if result.status_code == 429 or "rate limit" in lower or "too many requests" in lower:
            return "rate_limit"
        if result.status_code == 403 or "blocked" in lower or "access denied" in lower:
            return "ip_banned"
        if result.status_code == 401:
            return "auth_required"
        return None
