from __future__ import annotations

import re


class CaptchaDetector:
    CAPTCHA_PATTERNS = [
        r"g-recaptcha",
        r"h-captcha",
        r"cf-challenge",
        r"recaptcha",
        r"captcha",
        r"verify you are a human",
        r"are you a robot",
        r"cloudflare",
        r"ddos-guard",
        r"incapsula",
    ]

    def detect(self, html: str) -> bool:
        if not html:
            return False
        lower = html.lower()
        return any(re.search(p, lower) for p in self.CAPTCHA_PATTERNS)

    def identify_type(self, html: str) -> str | None:
        lower = html.lower()
        if re.search(r"g-recaptcha", lower):
            return "recaptcha"
        if re.search(r"h-captcha", lower):
            return "hcaptcha"
        if re.search(r"cf-challenge|cloudflare", lower):
            return "cloudflare"
        if re.search(r"captcha", lower):
            return "generic_captcha"
        return None
