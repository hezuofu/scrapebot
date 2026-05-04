from __future__ import annotations

import pytest

from scrapebot.middleware.anti_detect.captcha_detector import CaptchaDetector
from scrapebot.middleware.anti_detect.ban_detector import BanDetector
from scrapebot.types import DownloadResult


def test_captcha_detect_recaptcha():
    detector = CaptchaDetector()
    html = '<html><div class="g-recaptcha" data-sitekey="xxx"></div></html>'
    assert detector.detect(html) is True


def test_captcha_detect_cloudflare():
    detector = CaptchaDetector()
    html = "<html><body>cf-challenge running...</body></html>"
    assert detector.detect(html) is True


def test_captcha_detect_none():
    detector = CaptchaDetector()
    html = "<html><body>Normal page content</body></html>"
    assert detector.detect(html) is False


def test_ban_detect_403():
    detector = BanDetector()
    result = DownloadResult(url="http://test.com", status_code=403, text="")
    assert detector.detect(result) is True


def test_ban_detect_429():
    detector = BanDetector()
    result = DownloadResult(url="http://test.com", status_code=429, text="")
    assert detector.detect(result) is True


def test_ban_detect_text():
    detector = BanDetector()
    result = DownloadResult(url="http://test.com", status_code=200, text="Your IP has been blocked")
    assert detector.detect(result) is True


def test_ban_detect_normal():
    detector = BanDetector()
    result = DownloadResult(url="http://test.com", status_code=200, text="Welcome to our site")
    assert detector.detect(result) is False
