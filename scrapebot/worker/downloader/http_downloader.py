from __future__ import annotations

import logging
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx

from scrapebot.exceptions import DownloadError
from scrapebot.types import DownloadResult
from scrapebot.worker.downloader.base import BaseDownloader

logger = logging.getLogger(__name__)


class HTTPDownloader(BaseDownloader):
    def __init__(
        self,
        max_connections: int = 20,
        max_keepalive: int = 10,
        http2: bool = True,
        default_proxy: str | None = None,
    ) -> None:
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._http2 = http2
        self._default_proxy = default_proxy
        self._pools: dict[str, httpx.AsyncClient] = {}
        self._global_client: httpx.AsyncClient | None = None

    async def _get_client(self, url: str, proxy: str | None = None) -> httpx.AsyncClient:
        domain = self._domain_for(url)
        effective_proxy = proxy or self._default_proxy
        pool_key = f"{domain}|{effective_proxy or 'direct'}"

        if pool_key not in self._pools:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_keepalive,
            )
            mount: dict[str, httpx.AsyncHTTPTransport] | None = None
            if effective_proxy:
                transport = httpx.AsyncHTTPTransport(
                    proxy=effective_proxy,
                    limits=limits,
                    http2=self._http2,
                )
                mount = {"http://": transport, "https://": transport}

            self._pools[pool_key] = httpx.AsyncClient(
                limits=limits,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                http2=self._http2,
                mounts=mount,
            )

        return self._pools[pool_key]

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        proxy: str | None = None,
        timeout: float = 30.0,
        steps: list[dict[str, Any]] | None = None,
    ) -> DownloadResult:
        client = await self._get_client(url, proxy)
        start = time.monotonic()
        try:
            resp = await client.get(url, headers=headers, timeout=timeout)
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
        except httpx.TimeoutException as exc:
            raise DownloadError(f"Timeout: {url}") from exc
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return DownloadResult(url=url, elapsed_ms=round(elapsed, 2), error=str(exc))

    async def close(self) -> None:
        for client in self._pools.values():
            await client.aclose()
        self._pools.clear()

    @staticmethod
    def _domain_for(url: str) -> str:
        try:
            return urlparse(url).netloc
        except Exception:
            return url
