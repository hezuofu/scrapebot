class ScrapebotError(Exception):
    """Base exception for all scrapebot errors."""


class DownloadError(ScrapebotError):
    """Raised when a download fails."""


class ParseError(ScrapebotError):
    """Raised when parsing fails."""


class QueueError(ScrapebotError):
    """Raised when a queue operation fails."""


class StorageError(ScrapebotError):
    """Raised when a storage operation fails."""


class RateLimitError(ScrapebotError):
    """Raised when rate limit is exceeded."""


class ProxyError(ScrapebotError):
    """Raised when all proxies are exhausted or fail."""


class CircuitBreakerOpenError(ScrapebotError):
    """Raised when circuit breaker is open for a target."""


class CaptchaDetectedError(ScrapebotError):
    """Raised when a captcha is detected on the page."""


class BanDetectedError(ScrapebotError):
    """Raised when the target has banned or rate-limited the scraper."""


class ConfigError(ScrapebotError):
    """Raised for configuration issues."""


class TaskCancelledError(ScrapebotError):
    """Raised when a task is cancelled mid-execution."""


class MiddlewareError(ScrapebotError):
    """Raised when a middleware fails."""
