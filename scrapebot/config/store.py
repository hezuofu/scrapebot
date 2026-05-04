"""
Configuration persistence store.

Each config section self-registers via config/sections.py. ConfigStore
delegates load/serialize/default to the registered section handlers,
eliminating the if-elif chains that would otherwise grow with each new type.
"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from scrapebot.config.sections import (
    _REGISTRY,
    dataclass_sections,
    get_section,
)

logger = logging.getLogger(__name__)


class ConfigStore:
    def __init__(self, base_dir: str = "config") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {}
        self._dirty: set[str] = set()
        self._change_log: list[dict[str, Any]] = []

    # ── load / save ───────────────────────────────────────────

    def load_all(self) -> None:
        for name in _REGISTRY:
            self._load(name)

    def _load(self, name: str) -> None:
        section = get_section(name)
        if section is None:
            return
        try:
            self._data[name] = section.load(self._base_dir / section.filename)
        except Exception:
            logger.exception("Failed to load config section '%s'", name)
            self._data[name] = section.default()

    async def save(self, name: str) -> bool:
        async with self._lock:
            return self._save_sync(name)

    def _save_sync(self, name: str) -> bool:
        section = get_section(name)
        if section is None or name not in self._data:
            return False
        try:
            data = self._to_plain(section.serialize(self._data[name]))
            path = self._base_dir / section.filename
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._dirty.discard(name)
            self._log_change("save", name)
            return True
        except Exception:
            logger.exception("Failed to save config section '%s'", name)
            return False

    async def save_all(self) -> dict[str, bool]:
        return {name: await self.save(name) for name in list(self._dirty)}

    # ── generic accessors ─────────────────────────────────────

    def _get_or_default(self, name: str) -> Any:
        if name not in self._data:
            section = get_section(name)
            self._data[name] = section.default() if section else {}
        return self._data[name]

    def _get_serialized(self, name: str) -> dict[str, Any]:
        section = get_section(name)
        if section:
            return section.serialize(self._get_or_default(name))
        return {}

    # ── task templates ────────────────────────────────────────

    def get_task_config(self) -> dict[str, Any]:
        return self._get_serialized("task")

    def get_task_template(self, template_name: str) -> dict[str, Any] | None:
        from dataclasses import asdict
        cfg = self._get_or_default("task")
        if template_name in cfg.templates:
            return asdict(cfg.templates[template_name])
        return None

    async def save_task_template(self, template_name: str, data: dict[str, Any]) -> bool:
        async with self._lock:
            from scrapebot.config.task_config import TaskTemplate
            cfg = self._get_or_default("task")
            cfg.templates[template_name] = TaskTemplate(**data)
            self._dirty.add("task")
            return self._save_sync("task")

    async def delete_task_template(self, template_name: str) -> bool:
        async with self._lock:
            cfg = self._get_or_default("task")
            if template_name in cfg.templates:
                del cfg.templates[template_name]
                self._dirty.add("task")
                return self._save_sync("task")
            return False

    # ── proxy ─────────────────────────────────────────────────

    def get_proxy_config(self) -> dict[str, Any]:
        return self._get_serialized("proxy")

    async def update_proxy_config(self, data: dict[str, Any]) -> bool:
        return await self._update_dataclass("proxy", data)

    async def add_proxy_server(self, pool_name: str, server: dict[str, Any]) -> bool:
        async with self._lock:
            from scrapebot.config.proxy_config import ProxyPoolConfig, ProxyServer
            cfg = self._get_or_default("proxy")
            if pool_name not in cfg.pools:
                cfg.pools[pool_name] = ProxyPoolConfig()
            cfg.pools[pool_name].servers.append(ProxyServer(**server))
            self._dirty.add("proxy")
            return self._save_sync("proxy")

    async def remove_proxy_server(self, pool_name: str, host: str, port: int) -> bool:
        async with self._lock:
            cfg = self._get_or_default("proxy")
            if pool_name in cfg.pools:
                pool = cfg.pools[pool_name]
                before = len(pool.servers)
                pool.servers = [s for s in pool.servers if not (s.host == host and s.port == port)]
                if len(pool.servers) < before:
                    self._dirty.add("proxy")
                    return self._save_sync("proxy")
            return False

    # ── auth ──────────────────────────────────────────────────

    def get_auth_config(self) -> dict[str, Any]:
        return self._get_serialized("auth")

    async def save_site_auth(self, domain: str, site_data: dict[str, Any]) -> bool:
        async with self._lock:
            from scrapebot.config.auth_config import SiteAuth
            cfg = self._get_or_default("auth")
            cfg.sites[domain] = SiteAuth(**site_data)
            self._dirty.add("auth")
            return self._save_sync("auth")

    async def delete_site_auth(self, domain: str) -> bool:
        async with self._lock:
            cfg = self._get_or_default("auth")
            if domain in cfg.sites:
                del cfg.sites[domain]
                self._dirty.add("auth")
                return self._save_sync("auth")
            return False

    # ── storage ───────────────────────────────────────────────

    def get_storage_config(self) -> dict[str, Any]:
        return self._get_serialized("storage")

    async def update_storage_config(self, data: dict[str, Any]) -> bool:
        return await self._update_dataclass("storage", data)

    # ── rules ─────────────────────────────────────────────────

    def get_site_rules(self) -> dict[str, Any]:
        return deepcopy(self._get_or_default("site_rules"))

    def get_anti_ban_rules(self) -> dict[str, Any]:
        return deepcopy(self._get_or_default("anti_ban_rules"))

    def get_parse_rules(self) -> dict[str, Any]:
        return deepcopy(self._get_or_default("parse_rules"))

    async def update_site_rules(self, rules: dict[str, Any]) -> bool:
        return await self._update_dict("site_rules", rules)

    async def update_anti_ban_rules(self, rules: dict[str, Any]) -> bool:
        return await self._update_dict("anti_ban_rules", rules)

    async def update_parse_rules(self, rules: dict[str, Any]) -> bool:
        return await self._update_dict("parse_rules", rules)

    # ── import / export ───────────────────────────────────────

    def export_all(self) -> dict[str, Any]:
        result: dict[str, Any] = {"version": "1.0", "exported_at": datetime.now().isoformat()}
        for name in _REGISTRY:
            result[name] = self._get_serialized(name)
        return result

    async def import_all(self, data: dict[str, Any]) -> dict[str, bool]:
        async with self._lock:
            for name in _REGISTRY:
                if name in data:
                    self._dirty.add(name)
            return await self.save_all()

    # ── change log ────────────────────────────────────────────

    def get_change_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._change_log[-limit:]

    def _log_change(self, action: str, section: str, detail: str = "") -> None:
        self._change_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "section": section,
            "detail": detail,
        })
        if len(self._change_log) > 500:
            self._change_log = self._change_log[-500:]

    # ── internal helpers ──────────────────────────────────────

    async def _update_dataclass(self, name: str, data: dict[str, Any]) -> bool:
        async with self._lock:
            cfg = self._get_or_default(name)
            for key, value in data.items():
                if key == "pools":
                    from scrapebot.config.proxy_config import ProxyPoolConfig, ProxyServer
                    for p_name, p_data in value.items():
                        servers = [ProxyServer(**s) for s in p_data.pop("servers", [])]
                        cfg.pools[p_name] = ProxyPoolConfig(servers=servers, **p_data)
                elif hasattr(cfg, key):
                    setattr(cfg, key, value)
            self._dirty.add(name)
            return self._save_sync(name)

    async def _update_dict(self, name: str, data: dict[str, Any]) -> bool:
        async with self._lock:
            self._data[name] = data
            self._dirty.add(name)
            return self._save_sync(name)

    @staticmethod
    def _to_plain(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): ConfigStore._to_plain(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [ConfigStore._to_plain(v) for v in obj]
        if hasattr(obj, "value"):
            return obj.value
        return obj

    @property
    def dirty_sections(self) -> list[str]:
        return sorted(self._dirty)
