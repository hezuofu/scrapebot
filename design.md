scrapebot/
│
├── scheduler/                    # 调度层（核心）
│   ├── coordinator.py           # 核心协调器：任务分发、状态同步
│   ├── queue/                   # 队列实现
│   │   ├── priority_queue.py    # 优先级队列
│   │   ├── delayed_queue.py     # 延时/定时队列
│   │   └── redis_queue.py       # 分布式队列（Redis）
│   ├── dispatcher.py            # 任务分发器：将任务分配给worker
│   └── load_balancer.py         # 负载均衡：worker健康检查、任务分配策略
│
├── worker/                      # 执行层
│   ├── request_handler.py       # 请求处理器：策略路由
│   ├── downloader/              # 下载器模块
│   │   ├── base.py              # 下载器抽象接口
│   │   ├── http_downloader.py   # 简单HTTP下载（httpx/aiohttp）
│   │   ├── playwright_downloader.py  # 动态渲染（Playwright池）
│   │   └── selector.py          # 下载器选择策略（根据URL/规则自动切换）
│   ├── parser/                  # 解析器模块
│   │   ├── base.py              # 解析器接口
│   │   ├── css_parser.py        # CSS选择器解析
│   │   ├── xpath_parser.py      # XPath解析
│   │   ├── regex_parser.py      # 正则解析
│   │   ├── llm_parser.py        # AI智能解析（自然语言指令）
│   │   └── composite_parser.py  # 组合解析器（多策略fallback）
│   └── executor.py              # Worker执行器：协调下载+解析
│
├── middleware/                  # 中间件链
│   ├── chain.py                 # 中间件链管理器
│   ├── proxy/                   # 代理中间件
│   │   ├── rotator.py           # 代理轮换策略
│   │   └── pool.py              # 代理池管理
│   ├── headers/                 # 请求头中间件
│   │   ├── ua_rotator.py        # UA轮换/指纹生成
│   │   └── fingerprint.py       # 浏览器指纹模拟
│   ├── retry/                   # 重试中间件
│   │   ├── retry_policy.py      # 重试策略（指数退避等）
│   │   └── circuit_breaker.py   # 熔断器（目标站点故障保护）
│   ├── anti_detect/             # 反爬检测中间件
│   │   ├── captcha_detector.py  # 验证码检测
│   │   ├── ban_detector.py      # 封禁/限流检测
│   │   └── action_trigger.py    # 触发应对动作（换IP、降速等）
│   └── rate_limiter.py          # 限流中间件（令牌桶/漏桶）
│
├── pipeline/                    # 管道处理层
│   ├── base.py                  # Pipeline接口
│   ├── deduplication/           # 去重模块
│   │   ├── bloom_filter.py      # 布隆过滤器（内存）
│   │   ├── redis_dedup.py       # Redis去重（分布式）
│   │   └── lru_dedup.py         # LRU去重（有限内存）
│   ├── cleaning/                # 清洗模块
│   │   ├── field_cleaner.py     # 字段级清洗（去空格、格式化等）
│   │   ├── html_cleaner.py      # HTML标签清洗
│   │   └── validator.py         # 数据校验
│   ├── storage/                 # 存储适配器
│   │   ├── base.py              # 存储接口
│   │   ├── postgres.py          # PostgreSQL适配器
│   │   ├── mongodb.py           # MongoDB适配器
│   │   ├── s3.py                # S3/OSS适配器
│   │   └── kafka.py             # Kafka适配器（流式输出）
│   └── transformer.py           # 数据转换（字段映射、聚合等）
│
├── ai/                          # AI模块（现代化核心）
│   ├── llm_client.py            # LLM客户端封装（OpenAI/Claude/本地）
│   ├── instruction_parser.py    # 自然语言指令解析器
│   ├── dynamic_selector.py      # 动态选择器生成（AI自动写选择器）
│   ├── content_summarizer.py    # 内容摘要/分类
│   └── anomaly_detector.py      # 异常检测（识别页面结构变化）
│
├── monitoring/                  # 可观测性
│   ├── metrics/                 # 指标采集
│   │   ├── collector.py         # 指标收集器
│   │   ├── prometheus.py        # Prometheus导出
│   │   └── stats.py             # 统计信息（任务数、成功率、响应时间等）
│   ├── tracing/                 # 链路追踪
│   │   └── jaeger.py            # Jaeger集成
│   ├── logging/                 # 日志
│   │   ├── structured.py        # 结构化日志（JSON格式）
│   │   └── storage.py           # 日志存储（本地/ELK）
│   └── alerting/                # 告警
│       ├── rules.py             # 告警规则配置
│       └── notifier.py          # 通知（钉钉/邮件/webhook）
│
├── storage/                     # 持久化存储层
│   ├── task_store.py            # 任务状态存储（Redis/MySQL）
│   ├── checkpoint_store.py      # 断点续存存储
│   └── result_store.py          # 结果存储
│
├── api/                         # API层（可选）
│   ├── rest/                    # RESTful API
│   │   ├── routes.py            # 路由定义
│   │   ├── task_api.py          # 任务提交/查询/取消
│   │   └── stats_api.py         # 统计数据查询
│   └── webhook/                 # Webhook回调
│       └── callback.py          # 任务完成回调
│
├── config/                      # 配置管理
│   ├── settings.py              # 主配置（支持yaml/toml/env）
│   ├── scheduler_config.py      # 调度器配置
│   ├── worker_config.py         # Worker配置
│   └── rules/                   # 爬取规则配置
│       ├── site_rules.yaml      # 站点级规则（URL模式->解析器/下载器）
│       └── anti_ban_rules.yaml  # 反爬应对规则
│
├── scheduler/                   # （你图上已有，但补充细节）
│   └── ...（上面已列出）
│
└── main.py                      # 启动入口
