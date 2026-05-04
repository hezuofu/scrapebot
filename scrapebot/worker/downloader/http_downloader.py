from __future__ import annotations

import time

import httpx

from scrapebot.types import DownloadResult
from scrapebot.worker.downloader.base import BaseDownloader


class HTTPDownloader(BaseDownloader):
    def __init__(self, limits: httpx.Limits | None = None) -> None:
        self._client: httpx.AsyncClient | None = None
        self._limits = limits or httpx.Limits(max_connections=20)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=self._limits,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
    ) -> DownloadResult:
        client = await self._get_client()
        start = time.monotonic()
        try:
            resp = await client.get(
                url,
                headers=headers,
                proxy=proxy,
                timeout=timeout,
            )
            elapsed = (time.monotonic() - start) * 1000
            return DownloadResult(
                url=str(resp.url),
                status_code=resp.status_code,
                content=resp.content,
                text=resp.text,
                headers=dict(resp.headers),
                cookies=dict(resp.cookies),
                elapsed_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return DownloadResult(
                url=url,
                elapsed_ms=round(elapsed, 2),
                error=str(exc),
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
