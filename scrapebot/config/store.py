"""
Configuration persistence store.

All configs are backed by YAML files on disk, with in-memory caching
and auto-save. Supports CRUD operations for all config sections.
"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from scrapebot.config.auth_config import AuthConfig, SiteAuth
from scrapebot.config.proxy_config import ProxyConfig, ProxyPoolConfig, ProxyServer
from scrapebot.config.storage_config import StorageConfig
from scrapebot.config.task_config import TaskConfig, TaskTemplate

logger = logging.getLogger(__name__)


class ConfigStore:
    def __init__(self, base_dir: str = "config") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

        # In-memory configs
        self._task_config: TaskConfig | None = None
        self._proxy_config: ProxyConfig | None = None
        self._auth_config: AuthConfig | None = None
        self._storage_config: StorageConfig | None = None
        self._site_rules: dict[str, Any] = {}
        self._anti_ban_rules: dict[str, Any] = {}
        self._parse_rules: dict[str, Any] = {}

        self._dirty: set[str] = set()
        self._change_log: list[dict[str, Any]] = []

    # ── load / save ───────────────────────────────────────────

    def load_all(self) -> None:
        for name in ["task", "proxy", "auth", "storage", "site_rules", "anti_ban_rules", "parse_rules"]:
            self._load(name)

    def _load(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            if name == "task":
                from scrapebot.config.task_config import DEFAULT_TASK_CONFIG
                merged = deepcopy(DEFAULT_TASK_CONFIG)
                if data:
                    templates = {}
                    for t_name, t_data in data.get("templates", {}).items():
                        templates[t_name] = TaskTemplate(**t_data)
                    merged.templates = templates or merged.templates
                    for attr in ["default_timeout", "default_max_retries", "default_rate_limit",
                                  "max_concurrent_tasks", "task_queue_max_size", "result_ttl_seconds",
                                  "batch_size_limit"]:
                        if attr in data:
                            setattr(merged, attr, data[attr])
                self._task_config = merged
            elif name == "proxy":
                if data:
                    pools = {}
                    for p_name, p_data in data.get("pools", {}).items():
                        servers = [ProxyServer(**s) for s in p_data.pop("servers", [])]
                        pools[p_name] = ProxyPoolConfig(servers=servers, **p_data)
                    self._proxy_config = ProxyConfig(pools=pools, **{k: v for k, v in data.items() if k != "pools"})
            elif name == "auth":
                if data:
                    sites = {}
                    for s_name, s_data in data.get("sites", {}).items():
                        sites[s_name] = SiteAuth(**s_data)
                    self._auth_config = AuthConfig(sites=sites, **{k: v for k, v in data.items() if k != "sites"})
            elif name == "storage":
                if data:
                    self._storage_config = StorageConfig(**data)
            elif name == "site_rules":
                self._site_rules = data
            elif name == "anti_ban_rules":
                self._anti_ban_rules = data
            elif name == "parse_rules":
                self._parse_rules = data
        except Exception:
            logger.exception("Failed to load %s config from %s", name, path)

    async def save(self, name: str) -> bool:
        async with self._lock:
            return self._save_sync(name)

    def _save_sync(self, name: str) -> bool:
        path = self._path_for(name)
        try:
            data = self._to_plain(self._serialize(name))
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            self._dirty.discard(name)
            self._log_change("save", name)
            return True
        except Exception:
            logger.exception("Failed to save %s config", name)
            return False

    async def save_all(self) -> dict[str, bool]:
        results = {}
        for name in list(self._dirty):
            results[name] = await self.save(name)
        return results

    def _serialize(self, name: str) -> dict[str, Any]:
        if name == "task":
            cfg = self._task_config
            if cfg is None:
                from scrapebot.config.task_config import DEFAULT_TASK_CONFIG
                cfg = DEFAULT_TASK_CONFIG
            return {
                "templates": {n: asdict(t) for n, t in cfg.templates.items()},
                "default_timeout": cfg.default_timeout,
                "default_max_retries": cfg.default_max_retries,
                "default_rate_limit": cfg.default_rate_limit,
                "max_concurrent_tasks": cfg.max_concurrent_tasks,
                "task_queue_max_size": cfg.task_queue_max_size,
                "result_ttl_seconds": cfg.result_ttl_seconds,
                "batch_size_limit": cfg.batch_size_limit,
            }
        elif name == "proxy":
            cfg = self._proxy_config
            if cfg is None:
                from scrapebot.config.proxy_config import DEFAULT_PROXY_CONFIG
                cfg = DEFAULT_PROXY_CONFIG
            return {
                "enabled": cfg.enabled,
                "session_sticky": cfg.session_sticky,
                "auto_rotate_on_ban": cfg.auto_rotate_on_ban,
                "fallback_to_direct": cfg.fallback_to_direct,
                "pools": {n: asdict(p) for n, p in cfg.pools.items()},
            }
        elif name == "auth":
            cfg = self._auth_config
            if cfg is None:
                from scrapebot.config.auth_config import DEFAULT_AUTH_CONFIG
                cfg = DEFAULT_AUTH_CONFIG
            return {
                "sites": {n: asdict(s) for n, s in cfg.sites.items()},
                "default_session_path": cfg.default_session_path,
                "reauth_max_retries": cfg.reauth_max_retries,
            }
        elif name == "storage":
            cfg = self._storage_config
            if cfg is None:
                from scrapebot.config.storage_config import DEFAULT_STORAGE_CONFIG
                cfg = DEFAULT_STORAGE_CONFIG
            return asdict(cfg)
        elif name == "site_rules":
            return dict(self._site_rules)
        elif name == "anti_ban_rules":
            return dict(self._anti_ban_rules)
        elif name == "parse_rules":
            return dict(self._parse_rules)
        return {}

    # ── task config CRUD ──────────────────────────────────────

    def get_task_config(self) -> dict[str, Any]:
        return self._serialize("task")

    def get_task_template(self, name: str) -> dict[str, Any] | None:
        cfg = self._task_config
        if cfg and name in cfg.templates:
            return asdict(cfg.templates[name])
        return None

    async def save_task_template(self, name: str, template: dict[str, Any]) -> bool:
        async with self._lock:
            if self._task_config is None:
                from scrapebot.config.task_config import DEFAULT_TASK_CONFIG
                self._task_config = deepcopy(DEFAULT_TASK_CONFIG)
            self._task_config.templates[name] = TaskTemplate(**template)
            self._dirty.add("task")
            return self._save_sync("task")

    async def delete_task_template(self, name: str) -> bool:
        async with self._lock:
            if self._task_config and name in self._task_config.templates:
                del self._task_config.templates[name]
                self._dirty.add("task")
                return self._save_sync("task")
            return False

    # ── proxy config CRUD ─────────────────────────────────────

    def get_proxy_config(self) -> dict[str, Any]:
        return self._serialize("proxy")

    async def update_proxy_config(self, data: dict[str, Any]) -> bool:
        async with self._lock:
            if self._proxy_config is None:
                from scrapebot.config.proxy_config import DEFAULT_PROXY_CONFIG
                self._proxy_config = deepcopy(DEFAULT_PROXY_CONFIG)
            for key, value in data.items():
                if key == "pools":
                    for p_name, p_data in value.items():
                        servers_data = p_data.pop("servers", [])
                        servers = [ProxyServer(**s) for s in servers_data]
                        self._proxy_config.pools[p_name] = ProxyPoolConfig(servers=servers, **p_data)
                elif hasattr(self._proxy_config, key):
                    setattr(self._proxy_config, key, value)
            self._dirty.add("proxy")
            return self._save_sync("proxy")

    async def add_proxy_server(self, pool_name: str, server: dict[str, Any]) -> bool:
        async with self._lock:
            if self._proxy_config is None:
                from scrapebot.config.proxy_config import DEFAULT_PROXY_CONFIG
                self._proxy_config = deepcopy(DEFAULT_PROXY_CONFIG)
            if pool_name not in self._proxy_config.pools:
                from scrapebot.config.proxy_config import ProxyPoolConfig
                self._proxy_config.pools[pool_name] = ProxyPoolConfig()
            self._proxy_config.pools[pool_name].servers.append(ProxyServer(**server))
            self._dirty.add("proxy")
            return self._save_sync("proxy")

    async def remove_proxy_server(self, pool_name: str, host: str, port: int) -> bool:
        async with self._lock:
            if self._proxy_config and pool_name in self._proxy_config.pools:
                pool = self._proxy_config.pools[pool_name]
                before = len(pool.servers)
                pool.servers = [s for s in pool.servers if not (s.host == host and s.port == port)]
                if len(pool.servers) < before:
                    self._dirty.add("proxy")
                    return self._save_sync("proxy")
            return False

    # ── auth config CRUD ──────────────────────────────────────

    def get_auth_config(self) -> dict[str, Any]:
        return self._serialize("auth")

    async def save_site_auth(self, domain: str, site_auth: dict[str, Any]) -> bool:
        async with self._lock:
            if self._auth_config is None:
                from scrapebot.config.auth_config import DEFAULT_AUTH_CONFIG
                self._auth_config = deepcopy(DEFAULT_AUTH_CONFIG)
            self._auth_config.sites[domain] = SiteAuth(**site_auth)
            self._dirty.add("auth")
            return self._save_sync("auth")

    async def delete_site_auth(self, domain: str) -> bool:
        async with self._lock:
            if self._auth_config and domain in self._auth_config.sites:
                del self._auth_config.sites[domain]
                self._dirty.add("auth")
                return self._save_sync("auth")
            return False

    # ── storage config CRUD ───────────────────────────────────

    def get_storage_config(self) -> dict[str, Any]:
        return self._serialize("storage")

    async def update_storage_config(self, data: dict[str, Any]) -> bool:
        async with self._lock:
            if self._storage_config is None:
                from scrapebot.config.storage_config import DEFAULT_STORAGE_CONFIG
                self._storage_config = deepcopy(DEFAULT_STORAGE_CONFIG)
            for key, value in data.items():
                if hasattr(self._storage_config, key):
                    setattr(self._storage_config, key, value)
            self._dirty.add("storage")
            return self._save_sync("storage")

    # ── rules CRUD ────────────────────────────────────────────

    def get_site_rules(self) -> dict[str, Any]:
        return deepcopy(self._site_rules)

    def get_anti_ban_rules(self) -> dict[str, Any]:
        return deepcopy(self._anti_ban_rules)

    def get_parse_rules(self) -> dict[str, Any]:
        return deepcopy(self._parse_rules)

    async def update_site_rules(self, rules: dict[str, Any]) -> bool:
        async with self._lock:
            self._site_rules = rules
            self._dirty.add("site_rules")
            return self._save_sync("site_rules")

    async def update_anti_ban_rules(self, rules: dict[str, Any]) -> bool:
        async with self._lock:
            self._anti_ban_rules = rules
            self._dirty.add("anti_ban_rules")
            return self._save_sync("anti_ban_rules")

    async def update_parse_rules(self, rules: dict[str, Any]) -> bool:
        async with self._lock:
            self._parse_rules = rules
            self._dirty.add("parse_rules")
            return self._save_sync("parse_rules")

    # ── import / export ───────────────────────────────────────

    def export_all(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "task": self._serialize("task"),
            "proxy": self._serialize("proxy"),
            "auth": self._serialize("auth"),
            "storage": self._serialize("storage"),
            "site_rules": self._site_rules,
            "anti_ban_rules": self._anti_ban_rules,
            "parse_rules": self._parse_rules,
        }

    async def import_all(self, data: dict[str, Any]) -> dict[str, bool]:
        results: dict[str, bool] = {}
        async with self._lock:
            for section in ["task", "proxy", "auth", "storage", "site_rules", "anti_ban_rules", "parse_rules"]:
                if section in data:
                    self._dirty.add(section)
            results = await self.save_all()
        return results

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

    # ── helpers ───────────────────────────────────────────────

    def _path_for(self, name: str) -> Path:
        mapping = {
            "task": "task_config.yaml",
            "proxy": "proxy_config.yaml",
            "auth": "auth_config.yaml",
            "storage": "storage_config.yaml",
            "site_rules": "site_rules.yaml",
            "anti_ban_rules": "anti_ban_rules.yaml",
            "parse_rules": "parse_rules.yaml",
        }
        return self._base_dir / mapping.get(name, f"{name}.yaml")

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
