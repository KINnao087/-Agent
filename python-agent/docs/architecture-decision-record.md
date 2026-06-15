# 合同审核平台 — 架构决策记录 (ADR)

> 日期: 2026-06-15
> 项目: Python 合同审核 AI Agent → Java CRUD 全栈平台扩展

---

## 背景

现有 `PythonProject` 是一个基于 LangGraph + LangChain 的合同审核 AI Agent 项目:

- **CLI (Textual TUI)** 为主要交互方式
- **FastAPI** 仅暴露 1 个端点 (`POST /api/contracts/check-basic-info`)，无认证
- **文件系统** 存储审核产物 (`artifacts/reviews/`)，无关系型数据库
- **无用户系统**：无登录、注册、用户数据隔离

目标：套一个 Java 前后端壳子，使其成为标准的多用户 CRUD Web 应用。

---

## ADR-001: Java 框架选型

**决策**: Spring Boot 3.x

**候选方案**:

| 框架 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| Spring Boot | 生态最全、Spring Security 开箱即用、Spring Data JPA、学习资源最多 | 启动慢、内存占用大 | ✅ 选用 |
| Solon | 国产轻量、启动快、兼容部分 Spring 注解 | 生态小、周边工具少 | ❌ |
| Quarkus | 云原生、GraalVM 原生编译 | 生态较小、调试工具不成熟 | ❌ |

**理由**: 用户量级不大，启动速度不重要。生态丰富性和调试便利性优先。

---

## ADR-002: Java ↔ Python 通信方式

**决策**: HTTP REST + SSE（Server-Sent Events）

**候选方案**:

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| HTTP REST + SSE | 调试方便(Postman/curl)、已有 FastAPI 基础、标准协议 | 毫秒级 HTTP 开销 | ✅ 选用 |
| gRPC | 高性能二进制协议 | 需维护 proto 定义、调试需专门工具、LLM 瓶颈不在传输 | ❌ |
| 子进程调用 | 实现简单 | **致命缺陷**：每并发用户起一个独立 Python 进程；PaddleOCR 等 ML 模型重复加载(内存爆炸)；stdout/stderr 流式数据解析脆弱；无优雅取消机制 | ❌ |
| 消息队列 | 解耦彻底、适合高并发 | 需额外运维 RabbitMQ/Kafka、调试链路长、用户量不匹配 | ❌ |

**理由**:

1. 性能瓶颈在 LLM 响应速度（秒级），HTTP 毫秒级开销可忽略
2. 现有 `CliChatService.stream()` 已生成 `TraceEvent` 迭代器，改造成 SSE 成本极低
3. Python FastAPI 常驻进程，PaddleOCR/sentence-transformers 只加载一次
4. 流式事件与日志天然分离（SSE channel vs stderr），不会像子进程 stdout 那样互相污染
5. 任务取消走 `DELETE /api/tasks/{id}`，优雅停止

---

## ADR-003: 前端技术选型

**决策**: Vue 3 + Vite + TypeScript，前后端分离

**理由**: 用户指定 "标准的 Vue 前后端分离"。Spring Boot 不负责页面渲染。

---

## ADR-004: 前端布局设计

**决策**: 审核工作台型三栏布局（布局 A）

**候选方案**:

| 方案 | 描述 | 结论 |
|------|------|------|
| A: 审核工作台 | 左:合同列表 / 中:AI 执行追踪树 / 右:PDF 预览 | ✅ 选用 |
| B: 聊天交互型 | 左侧聊天记录 + 右侧聊天框，执行树嵌在气泡里 | ❌ 备选 |

**理由**: AI Agent 的 8 步审核流水线是**确定性的**，不需要用户反复对话。工作台三栏布局（合同列表 / 执行追踪树 / PDF 预览）比聊天框滚屏查找结果更高效。如果后期需要对话能力可以再加。

---

## ADR-005: 数据库选型

**决策**: MySQL 8.x

**候选方案**:

| 数据库 | 优点 | 结论 |
|--------|------|------|
| MySQL | 最主流、Spring Data JPA 支持最好、运维资料最多 | ✅ 选用 |
| PostgreSQL | JSON 字段更强大、全文搜索 | ❌ 过度，用户选 MySQL |
| H2(dev) → MySQL(prod) | 开发零配置 | ❌ 不需要，直接 MySQL |

**理由**: 用户指定 MySQL。Spring Boot + JPA + MySQL 是最成熟的组合。

---

## ADR-006: 项目结构与 IDE 策略

**决策**: Monorepo + 双 IDE（PyCharm + IDEA）

```
PythonProject/                  # 保持现有仓库名
├── python-agent/               # PyCharm 打开 → Python 项目
│   ├── core/                   # 现有代码（domain + application + infrastructure）
│   ├── server.py               # FastAPI 入口
│   └── pyproject.toml
├── java-backend/               # IDEA 打开 → Spring Boot
│   ├── pom.xml
│   └── src/main/java/com/contract/
├── vue-frontend/               # IDEA 内部 Vue 插件 → Vue 3
│   ├── package.json
│   └── src/
└── docker-compose.yml          # MySQL + 服务编排
```

**理由**:

- 一个人开发，monorepo 改功能可同时改三层
- PyCharm + IDEA 各干各的擅长领域，不过度绑定
- 两个 IDE 通过 HTTP 端口互通 (`localhost:8000` ↔ `localhost:8080` ↔ `localhost:5173`)
- Git 提交原子性：前后端改动在同一 commit

---

## ADR-007: Python 并发改造策略

**决策**: 去单例 + asyncio 线程池 + 文件锁

| 改动 | 位置 | 理由 |
|------|------|------|
| `ContractReviewService` 去单例化 | `core/application/reviews/service.py` | 每次请求 new 实例，避免状态互相覆盖 |
| `FileReviewStore` 加锁 | `core/infrastructure/reviews/file_store.py` | 按 `review_id` 粒度加锁 |
| FastAPI `async def` + `run_in_executor` | `core/presentation/api/` | 长时间 AI 调用不阻塞其他请求 |
| 任务取消机制 (`threading.Event`) | 新增 | 优雅取消，替代子进程的 `process.destroy()` |
| PaddleOCR 单例保持不变 | `core/infrastructure/text/paddle_ocr.py` | 已自带线程安全锁 |

**不动的部分**: domain 模型、AI prompts、seal detection、RAG、Tavily searcher、QCC scraper 全部保持不变。

---

## 总结

```
┌──────────────────────────────────────────────────────────────┐
│  技术栈总览                                                   │
├────────────┬─────────────────────────────────────────────────┤
│  前端      │ Vue 3 + Vite + TypeScript + Pinia + Axios       │
│  Java 后端  │ Spring Boot 3 + Spring Security + JPA + MySQL   │
│  Python AI │ FastAPI + LangGraph + LangChain + PaddleOCR      │
│  通信      │ HTTP REST (普通请求) + SSE (AI 流式事件)          │
│  数据库    │ MySQL 8.x (Java 侧), 文件系统 (Python 侧产物)     │
│  IDE       │ PyCharm (Python) + IDEA Ultimate (Java + Vue)    │
│  部署      │ Docker Compose (3 服务 + MySQL)                  │
└────────────┴─────────────────────────────────────────────────┘
```
