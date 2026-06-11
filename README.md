# 科技合同审核系统

该项目使用 LangGraph 编排合同处理流程，使用 LangChain 管理模型、Prompt、工具和结构化输出。

## 架构

```text
core/
  presentation/        CLI 和 FastAPI 入口
  application/
    workflows/         LangGraph 业务图
    contracts/         合同用例服务
    documents/         文档用例服务
    agent/             CLI Agent 和 LangChain Tools
  domain/              领域模型、归一化和字段比对规则
  infrastructure/
    ai/                ChatOpenAI、Prompt 和结构化输出 schema
    contracts/         AI 合同抽取与审核实现
    text/              OCR、PDF 和线性化
    vision/            印章视觉检测
    RAG/               本地规则检索
  shared/              路径和日志等通用能力
```

依赖方向：

```text
presentation -> application -> domain
                         -> infrastructure
shared 可被各层使用
```

`domain` 不依赖 LangChain、LangGraph、FastAPI、OCR 或视觉库。

## 业务图

- `documents.py`：加载文档 -> OCR 载荷 -> 结构化解析或线性化输出
- `basic_info.py`：基础信息提取 -> 平台字段比对 -> 汇总
- `integrity.py`：加载页面 -> 线性化 -> 印章候选检测 -> 完整性审核 -> 签章审核
- `cross_page_seal.py`：页面收集 -> 骑缝章片段检测 -> 规则分析 -> 多模态复审
- `validity.py`：合同主体提取 -> 公开信息搜索 -> 有效性风险审核
- `chat.py`：模型 -> LangChain ToolNode -> 模型的 CLI Agent 循环

## AI 层

- 模型工厂：[model.py](core/infrastructure/ai/model.py)
- 统一调用：[invoke.py](core/infrastructure/ai/invoke.py)
- Prompt：[prompts/](core/infrastructure/ai/prompts)
- 结构化响应：[schemas.py](core/infrastructure/ai/schemas.py)

模型通过 `ChatOpenAI` 连接 DashScope 的 OpenAI 兼容接口。结构化任务使用
`with_structured_output()`，不再维护自定义 provider、Agent 循环、消息裁剪或 JSON 修复器。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

PaddleOCR 的 CPU/GPU 后端应按运行机器单独选择安装。

创建 `.env`：

```text
AI_API_KEY=...
TAVILY_API_KEY=...
```

模型名称和 API 地址配置在 `config/config.json`。

## 运行

交互式 CLI：

```powershell
python main.py
```

结构化解析：

```powershell
python main.py parse --file <PDF或图片目录>
```

线性化：

```powershell
python main.py linearizer --file <PDF或图片目录> --output-dir output
```

HTTP 服务：

```powershell
python -m uvicorn server:app --reload
```

接口文档：`http://127.0.0.1:8000/docs`

## 测试

```powershell
python -m pytest -q
```

单元测试不访问真实 AI、OCR 或外部网络。真实链路脚本放在 `test/manual/`。
