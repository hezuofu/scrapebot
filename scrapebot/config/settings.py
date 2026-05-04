from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SchedulerSettings(BaseSettings):
    poll_interval: float = 0.5
    max_concurrent_tasks: int = 100
    default_priority: int = 0
    task_timeout: float = 60.0


class WorkerSettings(BaseSettings):
    pool_size: int = 10
    download_timeout: float = 30.0
    playwright_headless: bool = True
    playwright_pool_size: int = 3
    max_retries: int = 3


class RetrySettings(BaseSettings):
    max_attempts: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    retry_on_status: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])


class RateLimitSettings(BaseSettings):
    enabled: bool = True
    requests_per_second: float = 1.0
    burst_size: int = 5


class LLMSettings(BaseSettings):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.1


class APISettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class MonitoringSettings(BaseSettings):
    prometheus_port: int = 9090
    jaeger_endpoint: str = ""
    log_level: str = "INFO"
    log_format: str = "json"
    alert_webhook: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCRAPEBOT_",
        env_nested_delimiter="__",
        arbitrary_types_allowed=True,
    )

    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    api: APISettings = Field(default_factory=APISettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    site_rules: dict[str, Any] = Field(default_factory=dict)
    anti_ban_rules: dict[str, Any] = Field(default_factory=dict)
    parse_rules: dict[str, Any] = Field(default_factory=dict)

    _task_config: Any = None
    _proxy_config: Any = None
    _auth_config: Any = None
    _storage_config: Any = None

    @property
    def task(self) -> Any:
        if self._task_config is None:
            from scrapebot.config.task_config import DEFAULT_TASK_CONFIG
            self._task_config = DEFAULT_TASK_CONFIG
        return self._task_config

    @task.setter
    def task(self, value: Any) -> None:
        self._task_config = value

    @property
    def proxy_config(self) -> Any:
        if self._proxy_config is None:
            from scrapebot.config.proxy_config import DEFAULT_PROXY_CONFIG
            self._proxy_config = DEFAULT_PROXY_CONFIG
        return self._proxy_config

    @proxy_config.setter
    def proxy_config(self, value: Any) -> None:
        self._proxy_config = value

    @property
    def auth(self) -> Any:
        if self._auth_config is None:
            from scrapebot.config.auth_config import DEFAULT_AUTH_CONFIG
            self._auth_config = DEFAULT_AUTH_CONFIG
        return self._auth_config

    @auth.setter
    def auth(self, value: Any) -> None:
        self._auth_config = value

    @property
    def storage_config(self) -> Any:
        if self._storage_config is None:
            from scrapebot.config.storage_config import DEFAULT_STORAGE_CONFIG
            self._storage_config = DEFAULT_STORAGE_CONFIG
        return self._storage_config

    @storage_config.setter
    def storage_config(self, value: Any) -> None:
        self._storage_config = value


def load_settings(config_path: str | None = None) -> Settings:
    settings = Settings()
    if config_path:
        path = Path(config_path)
    else:
        path = Path("config.yaml")

    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        # Only pass simple fields to constructor, handle complex ones via properties
        simple_data = {k: v for k, v in data.items() if k in Settings.model_fields}
        settings = Settings(**simple_data)

    rules_dir = Path(__file__).parent / "rules"
    rule_files = {
        "site_rules": rules_dir / "site_rules.yaml",
        "anti_ban_rules": rules_dir / "anti_ban_rules.yaml",
        "parse_rules": rules_dir / "parse_rules.yaml",
    }
    for attr, path in rule_files.items():
        if path.exists():
            with open(path) as f:
                setattr(settings, attr, yaml.safe_load(f) or {})

    return settings
