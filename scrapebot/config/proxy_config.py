from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProxyProvider(str, Enum):
    STATIC = "static"
    ROTATING = "rotating"
    RESIDENTIAL = "residential"
    DATACENTER = "datacenter"
    MOBILE = "mobile"
    CUSTOM = "custom"


class ProxyProtocol(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


@dataclass
class ProxyServer:
    host: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: str = ""
    password: str = ""
    provider: ProxyProvider = ProxyProvider.STATIC
    location: str = ""
    max_failures: int = 3
    cooldown_seconds: float = 60.0
    weight: float = 1.0

    @property
    def url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"


@dataclass
class ProxyPoolConfig:
    provider: ProxyProvider = ProxyProvider.STATIC
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    rotation_strategy: str = "round_robin"
    max_failures: int = 3
    cooldown_seconds: float = 120.0
    health_check_interval: float = 30.0
    health_check_url: str = "https://httpbin.org/ip"
    min_pool_size: int = 3
    max_pool_size: int = 50
    servers: list[ProxyServer] = field(default_factory=list)


@dataclass
class ProxyConfig:
    enabled: bool = False
    default_pool: ProxyPoolConfig = field(default_factory=ProxyPoolConfig)
    pools: dict[str, ProxyPoolConfig] = field(default_factory=dict)
    session_sticky: bool = False
    auto_rotate_on_ban: bool = True
    fallback_to_direct: bool = True


DEFAULT_PROXY_CONFIG = ProxyConfig()
