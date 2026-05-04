from __future__ import annotations

from abc import ABC, abstractmethod

from scrapebot.types import DownloadResult


class BaseDownloader(ABC):
    @abstractmethod
    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> DownloadResult:
        """Download content from a URL and return the result."""
