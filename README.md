# PythonProject

科技合同审核项目，当前按分层架构组织。

## 架构总览

- `presentation` 只负责接收输入和返回输出
- `application` 只负责组织用例流程
- `domain` 只负责业务模型和业务规则
- `infrastructure` 只负责 AI、OCR、视觉、文件等技术实现
- `shared` 放跨层共用但不承载业务语义的工具

这样做的目的有三个：

1. 避免 CLI、HTTP、AI Prompt、业务规则、OCR 细节全部混在一个文件里
2. 避免上层直接穿透到底层实现，导致后续难以替换和测试
3. 让“科技合同审核”这个业务本身成为系统中心，而不是让某个框架或某个模型调用方式成为系统中心

```text
core/
  presentation/   CLI 和 HTTP 入口
  application/    用例编排层
  domain/         合同领域模型与规则
  infrastructure/ AI / OCR / 视觉等外部能力
  shared/         通用工具
```

## 分层思路

### 1. Presentation 层

职责：

- 接收外部输入
- 做参数解析、请求接收、结果返回
- 不承担业务规则
- 不直接编排 OCR、AI、印章检测等底层细节

当前目录：

```text
core/presentation/
  api/
    app.py
    routes/contracts.py
  cli/
    cli.py
    parse.py
    linearizer.py
```

当前含义：

- `core/presentation/cli/cli.py` 是 CLI 总入口
- `core/presentation/cli/parse.py` 和 `linearizer.py` 是具体命令适配器
- `core/presentation/api/app.py` 负责创建 FastAPI 应用
- `core/presentation/api/routes/contracts.py` 负责 HTTP 路由适配

这一层允许做的事：

- 解析命令行参数
- 定义 FastAPI route
- 调 application service
- 把结果打印成 JSON 或作为 HTTP 响应返回

这一层不应该做的事：

- 直接写合同字段比对规则
- 直接拼接复杂 AI 业务 Prompt
- 直接读 OCR 目录并做完整处理流程

### 2. Application 层

职责：

- 表达系统支持的“用例”
- 负责编排流程顺序
- 串联 domain 和 infrastructure
- 不承载底层技术实现细节

当前目录：

```text
core/application/
  contracts/
    basic_info_service.py
    integrity_service.py
  documents/
    ocr_payload.py
    parse_service.py
    linearize_service.py
```

当前含义：

- `contracts/basic_info_service.py`
  - 表达“合同基础信息核对”这个用例
  - 流程是：提取合同信息 -> 比对平台信息 -> 汇总结果
- `contracts/integrity_service.py`
  - 表达“合同完整性审核”这个用例
  - 流程是：构造页文本 -> 触发完整性审核 -> 如有需要再做签章审核
- `documents/ocr_payload.py`
  - 表达“把合同、附件、发票装配成统一 OCR payload”这个应用流程
- `documents/parse_service.py`
  - 表达“文档结构化解析”这个用例
- `documents/linearize_service.py`
  - 表达“文档线性化输出”这个用例

这一层的核心思想是：

- 一个 service 对应一个明确的业务动作
- 这一层只决定“先做什么、后做什么”
- 具体怎么 OCR、怎么调模型、怎么解析图片，都下沉给 infrastructure

### 3. Domain 层

职责：

- 承载科技合同审核的核心业务概念
- 定义领域对象、字段规范、比对规则、归一化规则
- 不依赖 FastAPI、CLI、OpenAI SDK、PaddleOCR、OpenCV 等技术实现

当前目录：

```text
core/domain/
  contracts/
    models.py
    integrity_models.py
    field_specs.py
    compare.py
    normalize.py
```

当前含义：

- `models.py`
  - 定义基础信息核对相关的请求模型、响应模型、比较结果模型
- `integrity_models.py`
  - 定义合同完整性审核相关的结果模型
- `field_specs.py`
  - 定义“哪些字段要核对、字段标签是什么、字段类型是什么”
- `compare.py`
  - 定义基础信息逐字段比对规则和 summary 汇总规则
- `normalize.py`
  - 定义日期、金额、电话、周期等归一化规则

这一层是整个项目最应该稳定的部分。

如果以后 CLI 换成 Web、AI 模型从 Qwen 换成别的、OCR 从 Paddle 换成别的，只要业务没变，domain 层原则上不应该跟着大改。

### 4. Infrastructure 层

职责：

- 对接一切外部技术能力
- 实现 AI 调用、OCR 解析、PDF 转图、印章检测、图像裁剪、配置加载等
- 为 application 层提供可调用的技术服务

当前目录：

```text
core/infrastructure/
  ai/
  contracts/
    basic_info_extractor.py
    integrity_review.py
  text/
    pdf2png.py
    ocr2json.py
    linearizer.py
    dolma_export.py
  vision/
    seal/
      detector.py
      preprocessing.py
      models.py
```

当前含义：

- `ai/`
  - 封装模型配置、provider、session、token 计算、消息裁剪、JSON 解析
- `contracts/basic_info_extractor.py`
  - 基于模型从合同文本中抽取 `contract_basic_info`
- `contracts/integrity_review.py`
  - 基于模型执行合同完整性审核和签章审核
- `text/ocr2json.py`
  - 处理 PNG/PDF -> OCR JSON
- `text/linearizer.py`
  - 把 OCR 结果变成可读的线性文本
- `vision/seal/detector.py`
  - 基于图像规则检测签章候选区域

这一层允许依赖：

- OpenAI SDK 或兼容 SDK
- PaddleOCR
- PyMuPDF
- OpenCV
- 文件系统
- 配置文件

但这一层不应该反向定义业务规则本身。

### 5. Shared 层

职责：

- 放通用工具
- 工具本身不属于某个业务领域

当前目录：

```text
core/shared/
  path_utils.py
```

当前含义：

- `path_utils.py` 负责路径解析、目录创建、按后缀列文件等通用能力

## 依赖方向

本项目要求依赖方向单向流动：

```text
presentation -> application -> domain
                         -> infrastructure

infrastructure 可以被 application 调用
domain 不应该依赖 presentation 和 infrastructure
shared 可以被各层使用
```

更具体一点：

- `presentation` 不应该直接写业务规则
- `application` 可以同时调用 `domain` 和 `infrastructure`
- `domain` 不能直接 import FastAPI、PaddleOCR、OpenAI provider、OpenCV
- `infrastructure` 负责技术细节，不负责定义“什么叫合同核对通过”

## 典型调用链

### 1. CLI 结构化解析调用链

```text
main.py
  -> core/presentation/cli/cli.py
  -> core/presentation/cli/parse.py
  -> core/application/documents/parse_service.py
  -> core/application/documents/ocr_payload.py
  -> core/infrastructure/text/*
  -> core/infrastructure/ai/*
```

含义：

- CLI 负责收参数
- application 负责组织“读取文件 -> 组装 OCR payload -> 调 AI 结构化”
- infrastructure 负责 OCR、线性化、模型调用

### 2. HTTP 基础信息核对调用链

```text
server.py
  -> core/presentation/api/app.py
  -> core/presentation/api/routes/contracts.py
  -> core/application/contracts/basic_info_service.py
  -> core/infrastructure/contracts/basic_info_extractor.py
  -> core/domain/contracts/compare.py
  -> core/domain/contracts/normalize.py
```

含义：

- API 层负责接收请求和返回响应
- application 层表达“核对基础信息”这个用例
- infrastructure 负责通过模型提取合同信息
- domain 负责按业务规则比对和汇总

### 3. 合同完整性审核调用链

```text
core/application/contracts/integrity_service.py
  -> core/infrastructure/text/linearizer.py
  -> core/infrastructure/contracts/integrity_review.py
  -> core/infrastructure/vision/seal/detector.py
  -> core/domain/contracts/integrity_models.py
```

含义：

- application 负责组织审核顺序
- infrastructure 负责模型审核和印章候选检测
- domain 负责承载审核结果的数据结构

## 当前设计取舍

当前项目虽然是“科技合同审核 agent”，但程序主入口并不是自由自然语言驱动，而是结构化入口驱动：

- CLI 适合批处理、调试、自动化执行
- HTTP API 适合平台集成
- AI 被放在用例内部承担“提取”和“审核判断”能力

这意味着本项目当前更接近：

- “分层的合同审核系统”
- 而不是“完全对话式驱动的一般 agent”

这是一个刻意的设计取舍。对合同审核这类需要稳定输入和可重复执行的场景，结构化入口比全自然语言入口更可控。

## 后续新增代码时的规则

后续开发建议严格遵守以下规则：

1. 新增 CLI/API 接口，只放到 `presentation`
2. 新增业务动作，优先放到 `application`
3. 新增合同规则、字段定义、归一化逻辑，只放到 `domain/contracts`
4. 新增 AI/OCR/视觉/文件系统适配，只放到 `infrastructure`
5. 不要在 `presentation` 里直接调用过多底层模块
6. 不要在 `domain` 里直接依赖模型 SDK、图像库、Web 框架
7. 公共工具若不包含业务语义，放到 `shared`

如果某个文件同时出现以下几类代码，通常就说明它职责过重，需要拆分：

- HTTP/CLI 参数解析
- 业务规则判断
- Prompt 拼接
- 模型调用
- OCR 文件遍历
- 图像处理
- 响应格式转换

## Entrypoints

- CLI: `python main.py ...`
- HTTP API: `uvicorn server:app --reload`

## Server Mode

本项目支持通过 FastAPI 以 server 模式启动。

### 1. 安装依赖

如果尚未安装 `uvicorn`，先在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install uvicorn
```

### 2. 启动服务

在项目根目录 `D:\pywork\PythonProject` 下执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --reload
```

### 3. 访问接口文档

服务启动后，可在浏览器中打开：

```text
http://127.0.0.1:8000/docs
```

### 4. 指定端口启动

如果需要自定义端口，例如 `9000`，执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 9000
```

此时接口文档地址为：

```text
http://127.0.0.1:9000/docs
```
