# 科技合同审核系统

该项目使用 LangGraph 编排主脑 AI 的工具调用循环，使用 LangChain 管理模型、Prompt、工具和结构化输出。固定的 OCR、字段核对和专项审核由普通应用服务执行。

## 架构

```text
core/
  presentation/        CLI 和 FastAPI 入口
  application/
    workflows/         仅保留 CLI Agent 的 LangGraph 对话图
    reviews/           review_id 审核任务、缓存、专项执行和报告
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

## 审核任务

主脑 AI 只看到业务级工具。`prepare_contract` 根据合同页面、附件、发票和平台数据生成材料指纹，创建或恢复 `review_id`。后续工具通过该编号共享 OCR、线性文本和专项结果：

- `check_basic_info`：基础信息提取和平台字段核对
- `check_text_integrity`：连续性、完整性、替换页和清晰度
- `check_contract_seals`：甲乙方普通签章
- `check_cross_page_seal`：骑缝章
- `check_contract_authenticity`：主体公开信息和有效性风险
- `write_review_report`：确定性生成 JSON 和 Markdown 报告

审核任务默认保存在 `artifacts/reviews/<review_id>/`。相同材料优先复用历史任务；模型、Prompt、OCR 或检测算法版本变化时，只失效受影响的专项和下游报告。

`workflows/chat.py` 是 application 层唯一的 LangGraph：模型 -> ToolNode -> 模型。

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
MAIN_AI_API_KEY=...
MAIN_AI_BASE_URL=...
MAIN_AI_MODEL=...

TEXT_AI_API_KEY=...
TEXT_AI_BASE_URL=...
TEXT_AI_MODEL=...

VISION_AI_API_KEY=...
VISION_AI_BASE_URL=...
VISION_AI_MODEL=...

TAVILY_API_KEY=...
```

三类 AI 配置必须按角色成组填写：`MAIN_AI_*` 用于主脑，
`TEXT_AI_*` 用于文本审核，`VISION_AI_*` 用于图片多模态审核。
某个角色的三个变量均留空时，会兼容回退到 `AI_API_KEY` 和
`config/config.json` 中的旧配置。

所有文档流程共用同一个输入适配器：

- PDF：按页渲染为 PNG
- PNG：直接使用
- JPG/JPEG、BMP、WebP：转换为 PNG
- 目录：按文件名顺序展开其中的受支持文件

转换结果写入输入路径旁的 `_normalized_images/`。

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
