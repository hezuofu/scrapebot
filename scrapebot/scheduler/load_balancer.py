from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from scrapebot.config.settings import Settings
from scrapebot.types import WorkerInfo

logger = logging.getLogger(__name__)


@dataclass
class WorkerLoad:
    worker_id: str
    active_tasks: int = 0
    total_tasks: int = 0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    last_updated: float = field(default_factory=time.monotonic)


class LoadBalancer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._workers: dict[str, WorkerInfo] = {}
        self._loads: dict[str, WorkerLoad] = {}
        self._lock = asyncio.Lock()
        self._health_task: asyncio.Task | None = None
        self._health_interval: float = 15.0
        self._stale_timeout: float = 30.0

    # ── registration ─────────────────────────────────────────

    async def register(self, worker: WorkerInfo) -> None:
        async with self._lock:
            self._workers[worker.id] = worker
            self._loads[worker.id] = WorkerLoad(worker_id=worker.id)
            logger.info("Worker registered: %s", worker.id)

    async def unregister(self, worker_id: str) -> None:
        async with self._lock:
            self._workers.pop(worker_id, None)
            self._loads.pop(worker_id, None)
            logger.info("Worker unregistered: %s", worker_id)

    async def heartbeat(self, worker_id: str) -> None:
        async with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].last_heartbeat = datetime.now()

    # ── load reporting ───────────────────────────────────────

    async def report_load(self, worker_id: str, active_tasks: int = 0,
                          cpu: float = 0.0, memory_mb: float = 0.0) -> None:
        async with self._lock:
            if worker_id in self._loads:
                ld = self._loads[worker_id]
                ld.active_tasks = active_tasks
                ld.cpu_percent = cpu
                ld.memory_mb = memory_mb
                ld.last_updated = time.monotonic()

    def score(self, worker_id: str) -> float:
        """Lower score = better candidate for receiving work."""
        ld = self._loads.get(worker_id)
        if ld is None:
            return 0.0
        return ld.active_tasks * 10 + ld.cpu_percent * 0.5 + (ld.memory_mb / 100)

    # ── selection ────────────────────────────────────────────

    async def select_worker(self, prefer_idle: bool = True) -> WorkerInfo | None:
        async with self._lock:
            alive = [w for w in self._workers.values()
                     if (datetime.now() - w.last_heartbeat).total_seconds() < self._stale_timeout]
            if not alive:
                return None

            if prefer_idle:
                idle = [w for w in alive if w.status == "idle"]
                candidates = idle or alive
            else:
                candidates = alive

            return min(candidates, key=lambda w: self.score(w.id), default=None)

    async def get_workers(self) -> list[WorkerInfo]:
        async with self._lock:
            return list(self._workers.values())

    async def get_loads(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return {
                wid: {
                    "active_tasks": ld.active_tasks,
                    "cpu_percent": ld.cpu_percent,
                    "memory_mb": ld.memory_mb,
                }
                for wid, ld in self._loads.items()
            }

    # ── health checking ──────────────────────────────────────

    async def start_health_checks(self) -> None:
        if self._health_task is not None:
            return
        self._health_task = asyncio.create_task(self._health_loop())

    async def stop_health_checks(self) -> None:
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None

    async def _health_loop(self) -> None:
        while True:
            await asyncio.sleep(self._health_interval)
            await self.check_health(self._stale_timeout)

    async def check_health(self, stale_timeout: float | None = None) -> list[str]:
        timeout = stale_timeout or self._stale_timeout
        now = datetime.now()
        stale: list[str] = []
        async with self._lock:
            for wid, w in list(self._workers.items()):
                if (now - w.last_heartbeat).total_seconds() > timeout:
                    stale.append(wid)
                    self._workers.pop(wid, None)
                    self._loads.pop(wid, None)
        if stale:
            logger.warning("Removed %d stale workers: %s", len(stale), stale)
        return stale

    # ── HPA metrics ──────────────────────────────────────────

    def hpa_queue_depth(self) -> int:
        total_active = sum(ld.active_tasks for ld in self._loads.values())
        return total_active

    def hpa_desired_replicas(self, target_tasks_per_worker: int = 10, min_replicas: int = 1,
                             max_replicas: int = 50) -> int:
        active = self.hpa_queue_depth()
        workers = max(len(self._workers), 1)
        desired = max(min_replicas, min(max_replicas, active // max(target_tasks_per_worker, 1)))
        return max(desired, workers) if active > workers * target_tasks_per_worker else workers

    def hpa_metrics(self, target_tasks_per_worker: int = 10) -> dict[str, Any]:
        return {
            "active_tasks": self.hpa_queue_depth(),
            "worker_count": len(self._workers),
            "avg_tasks_per_worker": (
                self.hpa_queue_depth() / max(len(self._workers), 1)
            ),
            "desired_replicas": self.hpa_desired_replicas(target_tasks_per_worker),
        }
