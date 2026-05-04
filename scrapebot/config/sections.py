"""Config sections registry — each config type self-registers its loader and serializer."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

import yaml

from scrapebot.config.auth_config import AuthConfig, SiteAuth, DEFAULT_AUTH_CONFIG
from scrapebot.config.proxy_config import ProxyConfig, ProxyPoolConfig, ProxyServer, DEFAULT_PROXY_CONFIG
from scrapebot.config.storage_config import StorageConfig, DEFAULT_STORAGE_CONFIG
from scrapebot.config.task_config import TaskConfig, TaskTemplate, DEFAULT_TASK_CONFIG


class ConfigSection(Protocol):
    name: str
    filename: str

    def load(self, path: Path) -> Any: ...
    def serialize(self, data: Any) -> dict[str, Any]: ...
    def default(self) -> Any: ...


class TaskSection:
    name = "task"
    filename = "task_config.yaml"

    def load(self, path: Path) -> TaskConfig:
        merged = deepcopy(DEFAULT_TASK_CONFIG)
        if not path.exists():
            return merged
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        templates = {}
        for t_name, t_data in data.get("templates", {}).items():
            templates[t_name] = TaskTemplate(**t_data)
        if templates:
            merged.templates = templates
        for attr in ["default_timeout", "default_max_retries", "default_rate_limit",
                      "max_concurrent_tasks", "task_queue_max_size", "result_ttl_seconds",
                      "batch_size_limit"]:
            if attr in data:
                setattr(merged, attr, data[attr])
        return merged

    def serialize(self, data: TaskConfig) -> dict[str, Any]:
        return {
            "templates": {n: asdict(t) for n, t in data.templates.items()},
            "default_timeout": data.default_timeout,
            "default_max_retries": data.default_max_retries,
            "default_rate_limit": data.default_rate_limit,
            "max_concurrent_tasks": data.max_concurrent_tasks,
            "task_queue_max_size": data.task_queue_max_size,
            "result_ttl_seconds": data.result_ttl_seconds,
            "batch_size_limit": data.batch_size_limit,
        }

    def default(self) -> TaskConfig:
        return deepcopy(DEFAULT_TASK_CONFIG)


class ProxySection:
    name = "proxy"
    filename = "proxy_config.yaml"

    def load(self, path: Path) -> ProxyConfig:
        if not path.exists():
            return deepcopy(DEFAULT_PROXY_CONFIG)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pools = {}
        for p_name, p_data in data.get("pools", {}).items():
            servers = [ProxyServer(**s) for s in p_data.pop("servers", [])]
            pools[p_name] = ProxyPoolConfig(servers=servers, **p_data)
        return ProxyConfig(
            pools=pools,
            **{k: v for k, v in data.items() if k != "pools"},
        )

    def serialize(self, data: ProxyConfig) -> dict[str, Any]:
        return {
            "enabled": data.enabled,
            "session_sticky": data.session_sticky,
            "auto_rotate_on_ban": data.auto_rotate_on_ban,
            "fallback_to_direct": data.fallback_to_direct,
            "pools": {n: asdict(p) for n, p in data.pools.items()},
        }

    def default(self) -> ProxyConfig:
        return deepcopy(DEFAULT_PROXY_CONFIG)


class AuthSection:
    name = "auth"
    filename = "auth_config.yaml"

    def load(self, path: Path) -> AuthConfig:
        if not path.exists():
            return deepcopy(DEFAULT_AUTH_CONFIG)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sites = {}
        for s_name, s_data in data.get("sites", {}).items():
            sites[s_name] = SiteAuth(**s_data)
        return AuthConfig(
            sites=sites,
            **{k: v for k, v in data.items() if k != "sites"},
        )

    def serialize(self, data: AuthConfig) -> dict[str, Any]:
        return {
            "sites": {n: asdict(s) for n, s in data.sites.items()},
            "default_session_path": data.default_session_path,
            "reauth_max_retries": data.reauth_max_retries,
        }

    def default(self) -> AuthConfig:
        return deepcopy(DEFAULT_AUTH_CONFIG)


class StorageSection:
    name = "storage"
    filename = "storage_config.yaml"

    def load(self, path: Path) -> StorageConfig:
        if not path.exists():
            return deepcopy(DEFAULT_STORAGE_CONFIG)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return StorageConfig(**data)

    def serialize(self, data: StorageConfig) -> dict[str, Any]:
        return asdict(data)

    def default(self) -> StorageConfig:
        return deepcopy(DEFAULT_STORAGE_CONFIG)


class RuleSection:
    def __init__(self, name: str, filename: str) -> None:
        self.name = name
        self.filename = filename

    def load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def serialize(self, data: dict[str, Any]) -> dict[str, Any]:
        return dict(data) if data else {}

    def default(self) -> dict[str, Any]:
        return {}


# Registry of all config sections
_REGISTRY: dict[str, ConfigSection] = {
    "task": TaskSection(),
    "proxy": ProxySection(),
    "auth": AuthSection(),
    "storage": StorageSection(),
    "site_rules": RuleSection("site_rules", "site_rules.yaml"),
    "anti_ban_rules": RuleSection("anti_ban_rules", "anti_ban_rules.yaml"),
    "parse_rules": RuleSection("parse_rules", "parse_rules.yaml"),
}


def get_section(name: str) -> ConfigSection | None:
    return _REGISTRY.get(name)


def all_section_names() -> list[str]:
    return list(_REGISTRY.keys())


def dataclass_sections() -> list[str]:
    return ["task", "proxy", "auth", "storage"]
