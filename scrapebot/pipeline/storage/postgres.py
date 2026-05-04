from __future__ import annotations

import json
import logging
from typing import Any

from scrapebot.pipeline.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class PostgresStorage(BaseStorage):
    def __init__(self, dsn: str = "", pool_min: int = 2, pool_max: int = 10) -> None:
        self._dsn = dsn
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool = None

    async def connect(self) -> None:
        if not self._dsn:
            return
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._pool_min,
                max_size=self._pool_max,
            )
            logger.info("PostgreSQL pool created: %s", self._dsn.split("@")[-1] if "@" in self._dsn else self._dsn)
        except ImportError:
            logger.warning("asyncpg not installed — PostgreSQL storage disabled")
        except Exception as exc:
            logger.error("Failed to connect to PostgreSQL: %s", exc)

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def save(self, data: list[dict[str, Any]], collection: str = "default") -> int:
        if not self._pool or not data:
            return 0
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._safe_name(collection)} (
                        id SERIAL PRIMARY KEY,
                        data JSONB NOT NULL DEFAULT '{{}}',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                count = 0
                async with conn.transaction():
                    for item in data:
                        await conn.execute(
                            f"INSERT INTO {self._safe_name(collection)} (data) VALUES ($1)",
                            json.dumps(item, ensure_ascii=False, default=str),
                        )
                        count += 1
                return count
        except Exception as exc:
            logger.error("PostgreSQL save failed: %s", exc)
            return 0

    async def query(
        self,
        collection: str = "default",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                query_str = f"SELECT data FROM {self._safe_name(collection)}"
                params: list[Any] = []
                if filters:
                    conditions = []
                    for i, (k, v) in enumerate(filters.items()):
                        conditions.append(f"data->>${i+1} = ${i+2}")
                        params.extend([k, str(v)])
                    query_str += " WHERE " + " AND ".join(conditions)
                query_str += f" ORDER BY created_at DESC LIMIT ${len(params)+1} OFFSET ${len(params)+2}"
                params.extend([limit, offset])
                rows = await conn.fetch(query_str, *params)
                return [json.loads(row["data"]) if isinstance(row["data"], str) else dict(row["data"])
                        for row in rows]
        except Exception as exc:
            logger.error("PostgreSQL query failed: %s", exc)
            return []

    async def delete(self, collection: str, filters: dict[str, Any]) -> int:
        if not self._pool:
            return 0
        try:
            async with self._pool.acquire() as conn:
                params: list[Any] = []
                conditions = []
                for i, (k, v) in enumerate(filters.items()):
                    conditions.append(f"data->>${i+1} = ${i+2}")
                    params.extend([k, str(v)])
                where = " WHERE " + " AND ".join(conditions) if conditions else ""
                result = await conn.execute(f"DELETE FROM {self._safe_name(collection)}{where}", *params)
                count = int(result.split()[-1]) if result else 0
                return count
        except Exception as exc:
            logger.error("PostgreSQL delete failed: %s", exc)
            return 0

    @staticmethod
    def _safe_name(name: str) -> str:
        # Allow only alphanumeric + underscore
        return "".join(c if c.isalnum() or c == "_" else "_" for c in name) or "default"
