# PythonProject

科技合同审核项目，当前按分层架构组织：

```text
core/
  presentation/   CLI 和 HTTP 入口
  application/    用例编排层
  domain/         合同领域模型与规则
  infrastructure/ AI / OCR / 视觉等外部能力
  shared/         通用工具
```

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
