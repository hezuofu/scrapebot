from __future__ import annotations

import re

from scrapebot.types import DownloadResult


class BanDetector:
    BAN_PATTERNS = [
        r"access denied",
        r"ip\s.*blocked",
        r"has been blocked",
        r"your request has been blocked",
        r"too many requests",
        r"rate limit exceeded",
        r"request denied",
        r"you have been blocked",
        r"unauthorized access",
    ]

    def detect(self, result: DownloadResult) -> bool:
        if result.status_code in (403, 401):
            return True
        if result.status_code == 429:
            return True
        lower = result.text.lower()
        return any(re.search(p, lower) for p in self.BAN_PATTERNS)

    def identify_reason(self, result: DownloadResult) -> str | None:
        lower = result.text.lower()
        if result.status_code == 429 or "rate limit" in lower or "too many requests" in lower:
            return "rate_limit"
        if result.status_code == 403 or "blocked" in lower or "access denied" in lower:
            return "ip_banned"
        if result.status_code == 401:
            return "auth_required"
        return None
