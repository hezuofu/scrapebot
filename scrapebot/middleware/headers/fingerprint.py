from __future__ import annotations

import random

from scrapebot.middleware.headers.ua_rotator import UARotator


class BrowserFingerprint:
    LANGUAGES = [
        "en-US,en;q=0.9",
        "en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "en-US,en;q=0.9,fr;q=0.8",
    ]

    SEC_CH_UA = [
        '"Chromium";v="138", "Not_A Brand";v="24"',
        '"Google Chrome";v="138", "Chromium";v="138", "Not_A Brand";v="24"',
        '"Chromium";v="137", "Not_A Brand";v="24"',
    ]

    def enrich(self, headers: dict[str, str]) -> dict[str, str]:
        enriched = dict(headers)
        ua = enriched.get("User-Agent", "")
        enriched.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        enriched.setdefault("Accept-Language", random.choice(self.LANGUAGES))
        enriched.setdefault("Accept-Encoding", "gzip, deflate, br")
        enriched.setdefault("Sec-Ch-Ua", random.choice(self.SEC_CH_UA))
        enriched.setdefault("Sec-Ch-Ua-Mobile", "?0")
        enriched.setdefault("Sec-Ch-Ua-Platform", UARotator.platform_for(ua))
        enriched.setdefault("Sec-Fetch-Dest", "document")
        enriched.setdefault("Sec-Fetch-Mode", "navigate")
        enriched.setdefault("Sec-Fetch-Site", "none")
        enriched.setdefault("Sec-Fetch-User", "?1")
        enriched.setdefault("Upgrade-Insecure-Requests", "1")
        enriched.setdefault("Cache-Control", "max-age=0")
        return enriched
