from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from scrapebot.config.settings import Settings
from scrapebot.types import Task, WorkerInfo

logger = logging.getLogger(__name__)


class LoadBalancer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = asyncio.Lock()

    async def register(self, worker: WorkerInfo) -> None:
        async with self._lock:
            self._workers[worker.id] = worker
            logger.info("Worker registered: %s", worker.id)

    async def unregister(self, worker_id: str) -> None:
        async with self._lock:
            self._workers.pop(worker_id, None)
            logger.info("Worker unregistered: %s", worker_id)

    async def heartbeat(self, worker_id: str) -> None:
        async with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].last_heartbeat = datetime.now()

    async def select_worker(self) -> WorkerInfo | None:
        async with self._lock:
            idle = [w for w in self._workers.values() if w.status == "idle"]
            if not idle:
                return None
            return min(idle, key=lambda w: w.tasks_completed)

    async def get_workers(self) -> list[WorkerInfo]:
        async with self._lock:
            return list(self._workers.values())

    async def check_health(self, stale_timeout: float = 30.0) -> list[str]:
        now = datetime.now()
        stale: list[str] = []
        async with self._lock:
            for wid, w in list(self._workers.items()):
                if (now - w.last_heartbeat).total_seconds() > stale_timeout:
                    stale.append(wid)
                    self._workers.pop(wid, None)
        if stale:
            logger.warning("Removed %d stale workers: %s", len(stale), stale)
        return stale
