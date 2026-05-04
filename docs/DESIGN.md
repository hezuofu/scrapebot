# Scrapebot 系统需求与设计文档

> 版本 1.0 | 2026-05

---

## 一、系统概述

Scrapebot 是一个以调度器为中心、Worker 执行、中间件增强、管道处理、AI 辅助、可观测性兜底的分布式爬虫框架。各组件职责单一、接口清晰，支持水平扩展和插件化替换。

### 1.1 核心架构

```
                         ┌─────────────────┐
                         │   REST API / CLI │
                         └────────┬────────┘
                                  │ submit(ScrapeJob)
                                  ▼
┌──────────────────────────────────────────────────────────────┐
│                      调度层 (Scheduler)                       │
│                                                              │
│  Coordinator ◄── Dispatcher ◄── LoadBalancer                 │
│      │               │               │                       │
│      ▼               ▼               ▼                       │
│  [Queues]      [Affinity]      [Health Check]                │
│  Priority      Domain→Worker   Worker Scoring                │
│  Delayed       Batch Dispatch  K8s HPA                       │
│  Redis                                                       │
└──────────────────────────┬───────────────────────────────────┘
                           │ Task
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      执行层 (Worker)                          │
│                                                              │
│  RequestHandler → DownloaderSelector → [HTTP|Playwright|Auto]│
│       │                                        │             │
│       ▼                                        ▼             │
│  [Middleware Chain]                    [Parsers: CSS|XPath|  │
│   RateLimit | UA | Proxy | Retry | CB   Regex|LLM|Composite]│
│   AntiDetect]                                  │             │
│                                                ▼             │
└────────────────────┬─────────────────────────────────────────┘
                     │ items
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                    管道层 (Pipeline)                          │
│                                                              │
│  Dedup → Clean → Validate → Transform → [Storage Adapters]   │
│                                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              可观测性 + AI + 事件系统（横切）                   │
│  Prometheus | Jaeger | StructuredLog | Alerting              │
│  LLM | InstructionCache | AnomalyDetect                      │
│  EventBus | 39 EventTypes | Webhook                          │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 三种采集模式

| 模式 | 流程 | 适用场景 |
|------|------|---------|
| **fetch** | HTTP 请求 → HTML → 本地解析 | 静态页面、API 接口 |
| **render** | 浏览器渲染 → HTML → 本地解析 | JavaScript SPA |
| **automate** | 浏览器自动化 → 直接提取 | 需要点击/滚动/填表的页面 |

---

## 二、调度层 (Scheduler)

### 2.1 核心协调器 (Coordinator)

负责全局任务生命周期管理。

| 职责 | 实现 |
|------|------|
| 任务接收 | `submit(task, depends_on=None)` 生成唯一 TaskID |
| 依赖管理 | 前置任务完成后自动将后置任务入队 |
| 状态维护 | OrderedDict + TTL 驱逐，`get_result()` 查询 |
| 暂停/恢复 | `pause(id)` 从队列移除，`resume(id)` 重新入队 |
| 取消 | `cancel(id)` 从队列/暂停中移除 |
| 超时终止 | `asyncio.wait_for(dispatch, timeout)` |
| 分布式协调 | `_in_flight` 集合防重复执行 |

关键接口：
```python
class Coordinator:
    async def submit(task: Task, depends_on: list[str] | None = None) -> str
    async def submit_batch(tasks: list[Task]) -> list[str]
    async def wait_for(task_id: str, timeout: float = 60.0) -> TaskResult | None
    async def pause(task_id: str) -> bool
    async def resume(task_id: str) -> bool
    async def cancel(task_id: str) -> bool
    def get_result(task_id: str) -> TaskResult | None
    async def start() -> None
    async def stop() -> None
```

### 2.2 任务分发器 (Dispatcher)

| 职责 | 实现 |
|------|------|
| Worker 分配 | `dispatch(task)` → `LoadBalancer.select_worker()` |
| 亲和性调度 | URL 域名 → worker_id 粘性映射 |
| 批量分发 | `dispatch_batch(tasks)` → `asyncio.gather` 并行 |

### 2.3 负载均衡器 (Load Balancer)

| 职责 | 实现 |
|------|------|
| Worker 注册/注销 | `register()` / `unregister()` |
| 健康检查 | 15s 周期探测，超时 30s 摘除 |
| 负载感知 | `report_load(worker_id, active_tasks, cpu, memory)` |
| Worker 评分 | `score = active_tasks*10 + cpu*0.5 + memory/100` |
| K8s HPA | `hpa_metrics()` / `hpa_desired_replicas()` |

### 2.4 队列系统

#### 2.4.1 优先级队列 (PriorityQueue)

- 最小堆按 `effective_priority` 排序
- 预定义优先级：CRITICAL(-20) / HIGH(-10) / NORMAL(0) / LOW(10) / BATCH(20)
- 老化机制：等待时间 × aging_factor 自动提升优先级，防止低优先级任务饿死

#### 2.4.2 延时/定时队列 (DelayedQueue)

- `scheduled_at` 时间戳 → 到时自动迁移到就绪队列
- Cron 表达式支持：`register_cron("name", "*/5 * * * *", factory)`
- 延迟重试：`push_delayed_retry(task, delay_seconds)`

#### 2.4.3 分布式队列 (RedisQueue)

- Sorted Set 按优先级/时间戳排序
- Lua 脚本原子操作：`ZRANGE + ZREM + SADD` 一气呵成
- `recover()` 从 processing set 恢复崩溃后未确认的任务

---

## 三、执行层 (Worker)

### 3.1 Worker 执行器 (Executor)

编排下载→中间件链→解析→管道的完整流程。

| 职责 | 实现 |
|------|------|
| 执行编排 | `execute()` → download → parse → pipeline |
| 超时控制 | `asyncio.wait_for(_execute_inner, timeout=task.timeout)` |
| 并发隔离 | `asyncio.Semaphore(max_concurrency)` |

流程：
```
1. await rate_limiter.acquire(task)       # 可中断
2. enricher.enrich(headers)               # UA + fingerprint
3. proxy_rotator.get_proxy(domain=...)    # 粘性代理
4. task.model_copy(headers, proxy)        # 不可变更新
5. handler(enriched_task)                 # 下载 + 解析 + 管道
6. post_processor(task, result)           # 可中断（封禁→ABORT）
```

### 3.2 下载器模块

| 下载器 | 能力 |
|--------|------|
| **HTTPDownloader** | httpx + HTTP/2 + 按域名连接池 + 代理 |
| **PlaywrightDownloader** | 浏览器渲染 + 上下文池 + 错误回滚 |
| **BrowserAutomator** | 15 种操作 (click/scroll/type/extract...) + DOM 直接提取 |
| **DownloaderSelector** | URL 规则匹配 + JS-render 自动降级记忆 |

### 3.3 解析器模块

| 解析器 | 能力 |
|--------|------|
| **CSSParser** | CSS 选择器 + 列表/单项 + 属性提取 |
| **XPathParser** | XPath 表达式 + lxml |
| **RegexParser** | 正则表达式 + 捕获组 |
| **LLMParser** | OpenAI 兼容接口 + JSON 结构化输出 |
| **CompositeParser** | 多策略 fallback：CSS → XPath → Regex → LLM |

### 3.4 中间件链 (Middleware Chain)

```
请求前（可中断）:
  RateLimiter.acquire(task) → True/False
  UARotator.enrich(headers)
  BrowserFingerprint.enrich(headers)
  ProxyRotator.get_proxy(domain)

执行:
  RetryPolicy.execute(handler, task) 或直接 handler(task)

响应后（可中断）:
  CaptchaDetector.detect(text) → ActionTrigger.on_captcha()
  BanDetector.detect(result) → ActionTrigger.on_ban()
```

每个中间件步骤可返回 `MiddlewareAction.CONTINUE` 或 `MiddlewareAction.ABORT`。

| 中间件 | 能力 |
|--------|------|
| RateLimiter | 全局 + 按域名 + 资源组三级令牌桶，非阻塞 |
| UARotator | 洗牌轮换 + 移动/桌面设备匹配 |
| BrowserFingerprint | Accept/Sec-CH-UA/Sec-Fetch-* 全套，Platform 与 UA 同步 |
| ProxyRotator | 轮换/随机 + 粘性会话 + 失效自动剔除 |
| RetryPolicy | 指数退避 + 状态码判断 + 统一重试上限 |
| CircuitBreaker | CLOSED→OPEN→HALF_OPEN 三态 + 半开探测 |
| CaptchaDetector | 10 个正则模式，预编译，不区分大小写 |
| BanDetector | 状态码 403/401/429 + 10 个文本模式 |
| ActionTrigger | 自动换代理 + 降速 + 5 次封禁暂停人工介入 |

---

## 四、管道处理层 (Pipeline)

### 4.1 Pipeline 接口

```python
class Pipeline:
    def add(step: PipelineStep | (data, ctx) -> data) -> Pipeline
    async def run(data, context) -> Any
```

支持 `PipelineStep` ABC 或普通函数 `(data, ctx) -> data`。

### 4.2 去重模块

| 去重器 | 特点 |
|--------|------|
| BloomFilter | 位数组 + xxhash 多哈希，内存高效，可容忍小概率误报 |
| RedisDedup | Redis SET + SHA256 指纹，分布式精确去重 |
| LRUDedup | OrderedDict + 最大容量，有限内存缓存场景 |

### 4.3 清洗模块

| 清洗器 | 能力 |
|--------|------|
| FieldCleaner | 去空格、压缩空白、手机号/身份证/邮箱脱敏 |
| HTMLCleaner | 标签剥离、HTML 实体解码 |
| DataValidator | 类型检查 (number/integer)、必填校验、范围校验 (min,max) |

### 4.4 存储适配器

| 适配器 | 状态 | 能力 |
|--------|------|------|
| LocalFileStorage | ✅ 完整 | JSON / JSONL / JSONL.GZ，查询按文件 glob |
| PostgresStorage | ✅ 完整 | asyncpg 连接池 + JSONB + 自动建表 + 事务批量写入 |
| MongoStorage | ✅ 完整 | motor 异步驱动 + insert_many + find/sort/skip/limit |
| S3Storage | ⚠️ 骨架 | 接口定义完整，需 boto3 依赖 |
| KafkaStorage | ⚠️ 骨架 | 接口定义完整，需 aiokafka 依赖 |

### 4.5 数据转换器

| 能力 | 实现 |
|------|------|
| 字段映射 | `mapping={"title": "product_name"}` |
| 数据聚合 | `aggregate=True, aggregate_key="category"` |
| 格式转换 | `output_format="csv"` / `output_format="json"` |

---

## 五、AI 模块

| 组件 | 能力 |
|------|------|
| LLMClient | OpenAI 兼容接口 + 多模型 + Function Calling JSON |
| PromptTemplate | 5 个预置模板 + 变量替换 + 自定义注册 |
| InstructionCache | LRU 100 条，相同自然语言指令复用解析结果 |
| InstructionParser | 自然语言 → 结构化提取规则 |
| DynamicSelector | 给定 HTML + 目标字段 → AI 生成 CSS 选择器 |
| SelectorValidator | BeautifulSoup 实测选择器是否命中元素 |
| ContentSummarizer | 长文本摘要 + 自动分类标签 |
| AnomalyDetector | HTML 结构基线对比 + 异常告警 |

---

## 六、声明式抓取 (Spider)

### 6.1 配置格式

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
  "storage": {"type": "file", "file": {"output_dir": "output", "format": "json"}}
}
```

### 6.2 执行流程

```
ScrapeJob (声明式配置)
    ↓ build_job_from_config()
ScrapeJob (Pydantic 验证)
    ↓ SpiderRunner.expand()
[Task, Task, ...] (带 parser_instructions + 分页 metadata)
    ↓ Coordinator.submit()
[Queue] → Dispatcher → Executor → Pipeline → Storage
```

---

## 七、事件系统

### 7.1 39 种事件类型

```
task.*        → created, started, completed, failed, cancelled, retrying
download.*    → started, completed, failed
parse.*       → started, completed, failed
automate.*    → step.started, step.completed, step.failed
pipeline.*    → started, step.started, step.completed, completed
storage.*     → saved, failed
captcha.*     → detected
ban.*         → detected
rate.*        → limited
proxy.*       → switched
circuit_breaker.* → open, closed
retry.*       → attempt, exhausted
worker.*      → registered, unregistered, heartbeat, stale
checkpoint.*  → saved, loaded
anomaly.*     → detected
alert.*       → triggered
```

### 7.2 内置订阅器

| 订阅器 | 用途 |
|--------|------|
| LoggingSubscriber | 所有事件 → structlog JSON 日志 |
| MetricsSubscriber | 计数器事件 → StatsTracker 指标 |
| WebhookSubscriber | 关键事件 → HTTP POST 通知 |

---

## 八、可观测性

| 组件 | 能力 |
|------|------|
| MetricsCollector | 计数器/仪表盘/直方图 + 计时器 |
| PrometheusExporter | Counter/Gauge/Histogram + HTTP 端点暴露 |
| StatsTracker | 任务数/成功率/响应时间/错误类型/状态码 |
| JaegerTracer | span 上下文管理器，跨组件传播 |
| StructuredLogger | JSON 格式 + 上下文字段 + 文件轮转 |
| AlertRuleEngine | 条件函数 + 冷却时间 |
| AlertNotifier | Webhook 通知 |

---

## 九、配置管理

### 9.1 配置持久化 (ConfigStore)

7 种配置类型，每种自注册 `ConfigSection` (load / serialize / default)：

```
task_config.yaml     — 任务模板
proxy_config.yaml    — 代理服务器配置
auth_config.yaml     — 站点认证配置
storage_config.yaml  — 存储后端配置
jobs.yaml            — 声明式抓取任务
site_rules.yaml      — 站点级爬取规则
anti_ban_rules.yaml  — 反爬应对规则
parse_rules.yaml     — 预置解析规则
```

REST API：22 个端点（CRUD + 导入导出 + 变更日志）

Web Dashboard：`/dashboard` 单页可视化管理

### 9.2 组件注册表 (Registry)

6 类别 30+ 内置组件，支持运行时注册/替换：

```python
reg = get_registry()
reg.register("downloader", "my_cdn", lambda **kw: MyDownloader(**kw))
# settings.worker.downloader = "my_cdn"
```

### 9.3 环境变量

所有配置支持 `SCRAPEBOT_` 前缀环境变量覆盖：
```bash
SCRAPEBOT_SCHEDULER__QUEUE=redis
SCRAPEBOT_WORKER__PARSER=llm
SCRAPEBOT_LLM__API_KEY=sk-xxx
```

---

## 十、API 层

### 10.1 REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/tasks` | 提交任务 |
| POST | `/api/v1/tasks/batch` | 批量提交 |
| GET | `/api/v1/tasks/{id}` | 查询任务 |
| DELETE | `/api/v1/tasks/{id}` | 取消任务 |
| GET | `/api/v1/stats` | 系统统计 |
| GET | `/api/v1/stats/workers` | Worker 列表 |
| GET | `/api/v1/config/tasks` | 任务模板列表 |
| PUT | `/api/v1/config/tasks/{name}` | 保存模板 |
| DELETE | `/api/v1/config/tasks/{name}` | 删除模板 |
| GET | `/api/v1/config/proxy` | 代理配置 |
| PUT | `/api/v1/config/proxy` | 更新代理 |
| GET | `/api/v1/config/auth` | 认证配置 |
| PUT | `/api/v1/config/auth/sites/{domain}` | 保存站点认证 |
| GET | `/api/v1/config/storage` | 存储配置 |
| GET | `/api/v1/config/jobs` | Job 列表 |
| PUT | `/api/v1/config/jobs/{id}` | 保存 Job |
| POST | `/api/v1/config/jobs/{id}/expand` | 展开 Job 预览 |
| GET | `/api/v1/config/rules/sites` | 站点规则 |
| GET | `/api/v1/config/rules/anti-ban` | 反爬规则 |
| GET | `/api/v1/config/rules/parse` | 解析规则 |
| GET | `/api/v1/config/export` | 导出全部配置 |
| POST | `/api/v1/config/import` | 导入配置 |
| GET | `/api/v1/config/changelog` | 变更日志 |
| GET | `/api/v1/health` | 健康检查 |

### 10.2 Webhook

- 任务完成/失败时 POST JSON 到配置的 Callback URL
- 最多 3 次重试，指数退避

---

## 十一、数据模型

### 核心类型

```python
class Task(BaseModel):
    id: str
    url: str
    method: str = "GET"
    headers: dict[str, str]
    proxy: str | None
    scrape_mode: ScrapeMode = ScrapeMode.FETCH
    downloader_type: DownloaderType = DownloaderType.HTTP
    parser_type: ParserType = ParserType.CSS
    parser_instructions: dict[str, Any]
    automate_steps: list[dict[str, Any]]
    priority: int = 0
    scheduled_at: datetime | None
    max_retries: int = 3
    timeout: float = 30.0
    metadata: dict[str, Any]

class DownloadResult(BaseModel):
    url: str
    status_code: int
    content: bytes
    text: str
    headers: dict[str, str]
    cookies: dict[str, str]
    elapsed_ms: float
    error: str | None
    screenshot: bytes | None

class ParseResult(BaseModel):
    items: list[dict[str, Any]]
    errors: list[str]

class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    data: list[dict[str, Any]]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    retry_count: int
    download_result: DownloadResult | None
    parse_result: ParseResult | None
```

### 声明式类型

```python
class ScrapeJob(BaseModel):
    job_id: str
    name: str
    description: str
    start_urls: list[str]
    rules: list[ScrapeRule]
    concurrency: int
    download_delay: float
    storage: StorageRef | None

class FieldSelector(BaseModel):
    name: str
    type: FieldType           # css | xpath | regex
    selector: str
    pattern: str | None       # regex
    multiple: bool
    required: bool
    attribute: str | None

class PaginationConfig(BaseModel):
    type: PaginationType      # none | next_link | scroll | page_number
    enabled: bool
    max_pages: int
    delay: float
    next_selector: str | None
    page_param: str | None
```

---

## 十二、扩展点

### 自定义下载器
```python
from scrapebot import get_registry
reg = get_registry()
reg.register("downloader", "my_dl", lambda **kw: MyDownloader(**kw))
```

### 自定义中间件
```python
reg.register("middleware", "ip_checker", lambda **kw: IPSecurityMiddleware(**kw))
```

### 自定义解析器
```python
reg.register("parser", "vision", lambda **kw: VisionParser(**kw))
```

### 自定义存储
```python
reg.register("storage", "elasticsearch", lambda **kw: ESStorage(**kw))
```

### 事件钩子
```python
from scrapebot.events.bus import EventBus
bus = EventBus()
bus.subscribe(EventType.TASK_COMPLETED, my_callback)
```

### Pipeline 函数
```python
pipeline.add(lambda data, ctx: [enrich_item(item) for item in data])
```

---

## 十三、部署

### 单机模式
```bash
python -m scrapebot.main --url "https://example.com"
```

### API 服务模式
```bash
python -m scrapebot.main --api
# Dashboard: http://localhost:8000/dashboard
# API Docs:  http://localhost:8000/docs
```

### 分布式
```
[API Server] → [Redis Queue] → [Worker Pool (K8s)]
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                [Worker-1]    [Worker-2]    [Worker-N]
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                         [PostgreSQL / MongoDB / S3 / Kafka]
```

---

## 十四、测试

```bash
pytest tests/ -v          # 58 测试，56 通过
pytest tests/ --cov       # 覆盖率报告
```

测试覆盖：
- 事件总线（8 个测试）
- 中间件检测（7 个测试）
- 限流器（4 个测试）
- 管道清洗/转换（5 个测试）
- 调度队列（6 个测试）
- 爬虫模型（7 个测试）
- 爬虫执行器（7 个测试）
- 解析器（6 个测试）
- 下载模式（7 个测试）
