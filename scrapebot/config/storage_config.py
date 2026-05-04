from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PostgresConfig:
    enabled: bool = False
    dsn: str = ""
    host: str = "localhost"
    port: int = 5432
    database: str = "scrapebot"
    username: str = ""
    password: str = ""
    pool_min: int = 2
    pool_max: int = 10
    ssl_mode: str = "prefer"
    auto_create_tables: bool = True
    batch_size: int = 1000


@dataclass
class MongoConfig:
    enabled: bool = False
    url: str = "mongodb://localhost:27017"
    database: str = "scrapebot"
    username: str = ""
    password: str = ""
    pool_min: int = 2
    pool_max: int = 10
    batch_size: int = 1000


@dataclass
class RedisConfig:
    enabled: bool = False
    url: str = "redis://localhost:6379/0"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    pool_min: int = 5
    pool_max: int = 20
    key_prefix: str = "scrapebot"
    result_ttl: int = 86400
    queue_ttl: int = 3600


@dataclass
class S3Config:
    enabled: bool = False
    endpoint: str = ""
    region: str = "us-east-1"
    bucket: str = ""
    prefix: str = "scrapebot/"
    access_key: str = ""
    secret_key: str = ""
    acl: str = "private"
    content_type: str = "application/json"


@dataclass
class KafkaConfig:
    enabled: bool = False
    brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    topic: str = "scrapebot"
    client_id: str = "scrapebot-producer"
    acks: str = "all"
    compression: str = "gzip"
    batch_size: int = 16384


@dataclass
class LocalStorageConfig:
    enabled: bool = True
    base_path: str = "data/"
    format: str = "jsonl"
    max_file_size_mb: int = 100
    rotate_on_size: bool = True


@dataclass
class StorageConfig:
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    mongodb: MongoConfig = field(default_factory=MongoConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    s3: S3Config = field(default_factory=S3Config)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    local: LocalStorageConfig = field(default_factory=LocalStorageConfig)
    default_output: str = "local"


DEFAULT_STORAGE_CONFIG = StorageConfig()
