# 合同审核平台

AI 驱动的科技合同审核系统，支持基础信息核对、文字完整性、印章检测、骑缝章、真实性等 8 步审核流水线。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│  Vue 3 前端 (localhost:5173)                                 │
│  登录 / 注册 / 合同管理 / 审核工作台 / SSE 实时执行树          │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP REST + SSE
┌──────────────────▼──────────────────────────────────────────┐
│  Spring Boot 后端 (localhost:8080)                           │
│  JWT 认证 / 用户管理 / 合同 CRUD / SSE 中继                   │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP REST
┌──────────────────▼──────────────────────────────────────────┐
│  Python FastAPI (localhost:8000)                             │
│  LangGraph AI Agent / 8 步审核流水线 / OCR / 印章检测         │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  MySQL 8.x (localhost:3306)                                  │
│  users + contracts 表                                       │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

```
PythonProject/
├── python-agent/          # Python AI 审核引擎 (PyCharm 打开)
│   ├── core/              # Clean Architecture
│   ├── server.py          # FastAPI 入口
│   └── main.py            # CLI 入口
├── java-backend/          # Spring Boot 后端 (IDEA 打开)
│   └── src/main/java/com/contract/
├── vue-frontend/          # Vue 3 前端 (IDEA 内开发)
│   └── src/
└── docker-compose.yml     # 一键启动
```

## 环境要求

| 组件 | 版本 |
|------|------|
| Java | 17+ |
| Maven | 3.9+ |
| Node.js | 18+ |
| Python | 3.11 - 3.12 |
| MySQL | 8.x |
| Git | 任意 |

## 快速开始（推荐：仅前端本地，后端容器化）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 AI API Key

# 2. 一键启动 MySQL + Python + Java
docker-compose up -d

# 3. 启动前端（本地开发）
cd vue-frontend
npm run dev
```

浏览器打开 http://localhost:5173

## 手动启动（全部本地）

### 1. 准备 MySQL

确保 MySQL 正在运行，然后创建数据库（Hibernate 会自动建表）：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS contract_review DEFAULT CHARACTER SET utf8mb4;"
```

### 2. 配置 Spring Boot

编辑 `java-backend/src/main/resources/application.yml`，修改数据库连接：

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/contract_review?...
    username: root
    password: 你的密码
```

### 3. 配置 Python AI

复制 `python-agent/.env.example` 为 `python-agent/.env`（如没有则新建），填入 API Key：

```env
MAIN_AI_API_KEY=sk-...
MAIN_AI_BASE_URL=https://api.deepseek.com
MAIN_AI_MODEL=deepseek-v4-flash

TEXT_AI_API_KEY=sk-...
TEXT_AI_BASE_URL=https://api.deepseek.com
TEXT_AI_MODEL=deepseek-v4-pro

VISION_AI_API_KEY=...
VISION_AI_BASE_URL=...
VISION_AI_MODEL=...

TAVILY_API_KEY=tvly-...
```

### 4. 安装依赖

```bash
# Python (首次运行)
cd python-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# Java (自动下载)
cd java-backend
mvn compile

# Vue
cd vue-frontend
npm install
```

### 5. 启动服务

**终端 1 — Python AI 服务：**

```bash
cd python-agent
.venv\Scripts\activate
uvicorn server:app --reload --port 8000
```

接口文档：http://localhost:8000/docs

**终端 2 — Spring Boot：**

```bash
cd java-backend
mvn spring-boot:run
```

启动后监听 http://localhost:8080

**终端 3 — Vue 前端：**

```bash
cd vue-frontend
npm run dev
```

打开 http://localhost:5173

### 6. 使用

1. 浏览器打开 http://localhost:5173
2. 点击注册 → 输入用户名/邮箱/密码 → 注册成功自动登录
3. 工作台 → 上传合同 → 填写名称和文件路径
4. 进入审核详情页 → 点击「开始审核」
5. 实时观看 AI 执行追踪树：每项审核步骤的进度和结果

## 独立运行 Python CLI

不启动 Java/前端，直接使用命令行交互：

```bash
cd python-agent
python main.py
```

进入 Textual TUI Shell，拖拽合同 PDF 进行审核。

## API 端点

### Java 后端 (8080)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 当前用户 |
| POST | `/api/contracts` | 创建合同 |
| GET | `/api/contracts` | 合同列表 |
| GET | `/api/contracts/{id}` | 合同详情 |
| POST | `/api/contracts/{id}/review` | 发起审核 (SSE) |
| GET | `/api/contracts/{id}/report` | 审核报告 |
| DELETE | `/api/contracts/{id}/review` | 取消审核 |

### Python AI 服务 (8000)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/contracts/check-basic-info` | 基础信息核对 |
| POST | `/api/reviews` | 创建审核任务 |
| GET | `/api/reviews/{id}/stream` | SSE 流式事件 |
| GET | `/api/reviews/{id}/status` | 审核进度 |
| GET | `/api/reviews/{id}/report` | 审核报告 |
| DELETE | `/api/reviews/{id}` | 取消审核 |

## 测试

```bash
# Python 单元测试
cd python-agent
python -m pytest test/unit/ -q

# Java 编译（无单独测试，联调验证）
cd java-backend
mvn compile

# Vue 类型检查
cd vue-frontend
npx vue-tsc --noEmit
```

## IDE 设置

- **PyCharm** — 打开 `python-agent/`，解释器指向 `.venv`
- **IDEA** — 打开项目根目录，`java-backend/` 作为 Maven 项目，`vue-frontend/` 用 Vue 插件
- 两个 IDE 同时开，各管各的，端口互通

## 相关文档

- [架构决策记录](docs/architecture-decision-record.md)
- [Phase 1 代码改动](python-agent/core/)
- [Phase 2 开发日志](docs/devlog-phase2-spring-boot.md)
