from __future__ import annotations

import re


class CaptchaDetector:
    _PATTERN = re.compile(
        r"g-recaptcha|h-captcha|cf-challenge|recaptcha|captcha|"
        r"verify you are a human|are you a robot|cloudflare|"
        r"ddos-guard|incapsula",
        re.IGNORECASE,
    )

    _TYPE_PATTERNS = {
        "recaptcha": re.compile(r"g-recaptcha", re.IGNORECASE),
        "hcaptcha": re.compile(r"h-captcha", re.IGNORECASE),
        "cloudflare": re.compile(r"cf-challenge|cloudflare", re.IGNORECASE),
    }

    def __init__(self, trigger: object = None) -> None:
        self._trigger = trigger

    def detect(self, html: str) -> bool:
        return bool(html and self._PATTERN.search(html))

    def identify_type(self, html: str) -> str | None:
        for name, pattern in self._TYPE_PATTERNS.items():
            if pattern.search(html):
                return name
        if self.detect(html):
            return "generic_captcha"
        return None
