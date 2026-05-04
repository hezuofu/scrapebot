from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuthMethod(str, Enum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    FORM = "form"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    COOKIE = "cookie"
    SESSION = "session"


@dataclass
class BasicAuth:
    username: str
    password: str


@dataclass
class FormAuth:
    login_url: str
    username_field: str = "username"
    password_field: str = "password"
    username: str = ""
    password: str = ""
    extra_fields: dict[str, str] = field(default_factory=dict)
    submit_selector: str = "button[type=submit]"
    success_indicator: str = ""
    success_url_pattern: str = ""


@dataclass
class OAuth2Config:
    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""
    refresh_url: str = ""
    scope: str = ""
    access_token: str = ""
    refresh_token: str = ""


@dataclass
class CookieAuth:
    cookies: dict[str, str] = field(default_factory=dict)
    cookie_file: str = ""
    domain: str = ""


@dataclass
class SessionConfig:
    session_id: str = ""
    session_file: str = ""
    storage_path: str = "sessions/"
    auto_save: bool = True
    restore_on_start: bool = True


@dataclass
class SiteAuth:
    domain: str = ""
    method: AuthMethod = AuthMethod.NONE
    basic: BasicAuth | None = None
    form: FormAuth | None = None
    oauth2: OAuth2Config | None = None
    cookie: CookieAuth | None = None
    session: SessionConfig | None = None
    headers: dict[str, str] = field(default_factory=dict)
    login_required_urls: list[str] = field(default_factory=list)
    reauth_on_status: list[int] = field(default_factory=lambda: [401, 403])


@dataclass
class AuthConfig:
    sites: dict[str, SiteAuth] = field(default_factory=dict)
    default_session_path: str = "sessions/"
    session_encryption_key: str = ""
    reauth_max_retries: int = 2


DEFAULT_AUTH_CONFIG = AuthConfig()
