from __future__ import annotations

import random

DEFAULT_USER_AGENTS = [
    # Windows — Chrome (2026 era)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
    # Windows — Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    # macOS — Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    # macOS — Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    # Linux — Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
]

# Map UA substring → Sec-Ch-Ua-Platform value
PLATFORM_MAP = [
    ("Windows", '"Windows"'),
    ("Macintosh", '"macOS"'),
    ("Linux", '"Linux"'),
]


MOBILE_AGENTS = [
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.110 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 15; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.90 Mobile Safari/537.36",
]


class UARotator:
    def __init__(self, custom_agents: list[str] | None = None) -> None:
        self._agents = custom_agents or DEFAULT_USER_AGENTS
        self._mobile_agents = MOBILE_AGENTS
        self._index = 0
        self._shuffled: list[str] = []

    def get_random(self) -> str:
        return random.choice(self._agents)

    def for_device(self, device: str = "desktop") -> str:
        """Select UA matching target device type."""
        pool = self._mobile_agents if device == "mobile" else self._agents
        return random.choice(pool)

    def next(self) -> str:
        if not self._shuffled:
            self._shuffled = list(self._agents)
            random.shuffle(self._shuffled)
            self._index = 0
        ua = self._shuffled[self._index]
        self._index += 1
        if self._index >= len(self._shuffled):
            self._shuffled = []
        return ua

    def enrich(self, headers: dict[str, str]) -> dict[str, str]:
        if "User-Agent" not in headers:
            ua = self.next()
            headers = {**headers, "User-Agent": ua, "x-sb-ua-device": self._device_for(ua)}
        return headers

    @staticmethod
    def platform_for(ua: str) -> str:
        for keyword, platform in PLATFORM_MAP:
            if keyword in ua:
                return platform
        return '"Windows"'

    @staticmethod
    def _device_for(ua: str) -> str:
        if any(k in ua for k in ("Android", "iPhone", "Mobile")):
            return "mobile"
        return "desktop"
