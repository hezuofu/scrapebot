# Scrapebot

A distributed web scraping framework with scheduler-centric architecture, pluggable middleware, pipeline processing, AI-assisted parsing, and built-in observability.

## Compliance & Responsible Use

**Read before using this tool.**

### Legal

1. **Comply with all applicable laws** in your jurisdiction and the target site's jurisdiction, including data protection and privacy regulations
2. **Do not scrape personally identifiable information (PII)** without explicit consent
3. **Do not scrape copyrighted content** for unauthorized redistribution or commercial use
4. **Obtain proper authorization** before scraping systems related to critical infrastructure or national security

### Robots.txt

5. **Respect `robots.txt`** — check `/robots.txt` before scraping; do not crawl paths listed under `Disallow`
6. **Honor `Crawl-delay`** — control request rate to avoid overloading target servers
7. **Check `<meta name="robots">` tags** — respect page-level `noindex` / `nofollow` directives

### Fair Use

8. **Set reasonable request intervals** — default `download_delay` should be at least 1 second
9. **Use an honest User-Agent** — identify your crawler and provide contact information
10. **Read the Terms of Service** — do not violate the target site's ToS
11. **Only collect publicly accessible data** — do not bypass login walls, paywalls, or CAPTCHAs
12. **Respect data ownership** — use scraped data only for legitimate purposes
13. **Honor cease-and-desist requests** — stop scraping and remove data when asked

### Disclaimer

> This tool is intended for lawful data collection (search indexing, academic research, public data analysis, etc.).
> Users assume full legal responsibility for their actions. The author is not liable for any misuse.

---

## Architecture

```
API/CLI → Coordinator → [Priority|Delayed|Redis Queue] → Dispatcher → LoadBalancer
                                │
              ┌─────────────────┘
              ▼
       Executor ← MiddlewareChain (RateLimit → UA → Proxy → Retry → CB → AntiDetect)
              │
              ▼
       DownloaderSelector → [HTTP | Playwright | Automator]
              │
              ▼
       Parser [CSS | XPath | Regex | LLM | Composite]
              │
              ▼
       Pipeline [Dedup → Clean → Validate → Transform → StorageSink]
              │
              ▼
       Storage [LocalFile | PostgreSQL | MongoDB | S3 | Kafka]
```

## Quick Start

### Requirements

| Dependency | Version | Notes |
|------------|---------|-------|
| Python | **≥ 3.12** | Required — uses `X | None` syntax, `TaskGroup`, etc. |
| Redis | ≥ 6.0 | Optional, for distributed queues and dedup |
| PostgreSQL | ≥ 14 | Optional, for relational storage |
| MongoDB | ≥ 5.0 | Optional, for document storage |
| Playwright | via pip | Optional, for dynamic rendering and automation |

### Install

```bash
# Core
pip install httpx pydantic pydantic-settings pyyaml redis fastapi uvicorn \
    lxml beautifulsoup4 xxhash structlog prometheus-client openai

# Optional
pip install asyncpg motor         # database storage
pip install playwright && playwright install chromium  # browser rendering
pip install boto3                 # S3 storage
pip install aiokafka              # Kafka output
```

### Run

```bash
python -m scrapebot.main --url "https://example.com"

python -m scrapebot.main --api
# Dashboard: http://localhost:8000/dashboard
# API docs:  http://localhost:8000/docs
# Metrics:   http://localhost:8000/metrics

python -m scrapebot.main --list-components
```

## Three Scrape Modes

```python
from scrapebot.types import Task, ScrapeMode

# fetch — HTTP request → HTML → local parse
Task(url="https://example.com", scrape_mode=ScrapeMode.FETCH)

# render — browser render → HTML → local parse
Task(url="https://spa-site.com", scrape_mode=ScrapeMode.RENDER)

# automate — browser automation → direct extraction
Task(
    url="https://example.com/login",
    scrape_mode=ScrapeMode.AUTOMATE,
    automate_steps=[
        {"action": "type", "selector": "#username", "value": "user"},
        {"action": "click", "selector": "#login"},
    ]
)
```

## Declarative Jobs

```json
{
  "task_id": "quotes_spider",
  "task_name": "Quotes Spider",
  "start_urls": ["https://quotes.toscrape.com"],
  "rules": [{
    "url": "https://quotes.toscrape.com",
    "selectors": [
      {"name": "quote", "type": "css", "selector": ".text::text", "multiple": true},
      {"name": "author", "type": "xpath", "selector": "//small[@class='author']/text()", "multiple": true}
    ],
    "pagination_type": "next_link",
    "pagination_enabled": true,
    "pagination_max_pages": 10,
    "pagination_next_selector": "li.next a::attr(href)"
  }],
  "concurrency": 2,
  "download_delay": 1,
  "storage": {"type": "file", "file": {"output_dir": "output", "format": "json"}}
}
```

Submit via API:

```bash
curl -X PUT http://localhost:8000/api/v1/config/jobs/quotes_spider \
  -H "Content-Type: application/json" -d @job.json
```

## Pluggable Components

Every component is replaceable at runtime via the Registry.

```python
from scrapebot import get_registry
reg = get_registry()

reg.register("downloader", "my_cdn", lambda **kw: MyDownloader(**kw))
reg.register("parser", "vision", lambda **kw: VisionParser(**kw))
reg.register("storage", "elasticsearch", lambda **kw: ESStorage(**kw))
```

6 categories, 30+ built-in components:

```
queue:         priority | delayed | redis
downloader:    http | playwright | automator
parser:        css | xpath | regex | llm | composite
pipeline_step: field_cleaner | html_cleaner | validator | transformer |
               bloom_dedup | lru_dedup | redis_dedup
storage:       file | postgres | mongodb | s3 | kafka
middleware:    rate_limiter | ua_rotator | fingerprint | proxy_rotator |
               retry_policy | circuit_breaker | captcha_detector |
               ban_detector | action_trigger
```

## Event System

39 lifecycle event types with pub/sub, history, and blocking wait.

```python
from scrapebot.events.bus import EventBus
from scrapebot.events.types import EventType

bus = EventBus()
bus.subscribe(EventType.TASK_COMPLETED, handler)
bus.on_all(catch_all)
result = await bus.wait_for(EventType.TASK_COMPLETED, task_id="abc")
```

## Configuration

```bash
SCRAPEBOT_SCHEDULER__QUEUE=redis
SCRAPEBOT_SCHEDULER__MAX_CONCURRENT_TASKS=50
SCRAPEBOT_WORKER__PARSER=llm
SCRAPEBOT_WORKER__PIPELINE_STEPS='["field_cleaner","bloom_dedup","validator"]'
SCRAPEBOT_LLM__API_KEY=sk-xxx
SCRAPEBOT_MONITORING__LOG_LEVEL=DEBUG
```

## Rules & Warnings

### Must Follow

1. **Python ≥ 3.12** required — uses `X | None`, `asyncio.TaskGroup`, and other 3.12+ features
2. **Task objects are immutable** — middleware creates copies via `model_copy(update={...})`, never mutate `task.headers` directly
3. **All I/O must be async** — never use `open()`, `requests`, or sync `redis` inside a coroutine
4. **Downloader interfaces are separate** — `fetch/render` use `select_downloader()` → `BaseDownloader`, `automate` uses `select_automator()` → `BrowserAutomator`
5. **Enrichers return new dicts** — `enrich(headers)` must return a new dict, not mutate the input

### Configuration Rules

6. **Environment variables take precedence** — all `Settings` fields can be overridden via `SCRAPEBOT_` prefix
7. **Runtime configs are gitignored** — `config/*.yaml` (except `rules/`) should not be committed
8. **Never commit secrets** — API keys, passwords, and proxy credentials must use env vars or gitignored config files

### Runtime Rules

9. **Playwright requires browser install** — run `playwright install chromium` before first use
10. **Redis/PostgreSQL/MongoDB default to localhost** — override in production
11. **StorageSink must be the last pipeline step** — data should be cleaned and validated before persistence
12. **MiddlewareChain is injected via Executor** — do not bypass middleware by calling Executor directly from Dispatcher

### Development Rules

13. **Register new components** — call `reg.register(category, name, factory)` after implementing a class
14. **PipelineStep subclasses must implement `async process()`** — otherwise `pipeline.run()` crashes at runtime
15. **Use custom exceptions from `scrapebot.exceptions`** — avoid bare `raise Exception("...")`
16. **Async tests need `@pytest.mark.asyncio`** — and `pytest-asyncio` must be installed
17. **Run `pytest tests/ -q` before committing** — all 58 tests must pass

### Known Limitations

- S3 / Kafka adapters require extra dependencies (`boto3` / `aiokafka`)
- `WebhookCallback` and `WebhookSubscriber` activate only when `alert_webhook` URL is set
- Distributed worker mode requires Redis as the message broker
- `BrowserAutomator.extract` is invoked via `{"action": "extract", "instructions": {...}}` in steps

## Tests

```bash
pytest tests/ -v      # 58 tests
pytest tests/ --cov    # with coverage
```

## License

MIT
