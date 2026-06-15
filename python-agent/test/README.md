# 测试目录规范

`test/` 目录按用途拆分，避免 pytest 测试、人工调试脚本、输入样例和生成输出混在一起。新增测试或样例文件时，优先按本文规范摆放。

## 目录职责

```text
test/
  unit/       pytest 默认收集并运行的单元测试
  manual/     人工运行的调试脚本和端到端链路脚本
  fixtures/   可提交到仓库的小型稳定测试样例
  testfiles/  较大的本地合同样例，默认不提交
  output/     临时输出目录，默认不提交
```

### `unit/`

放可由 `pytest` 自动运行的测试。这里的测试应满足：

- 不依赖真实网络、真实 AI、真实 API 服务或人工输入。
- 不依赖本机固定绝对路径。
- 不把生成文件写回源码目录；需要文件输出时使用 `tmp_path`。
- 文件名使用 `test_*.py`。
- 按被测层次和模块归档。

推荐结构：

```text
test/unit/domain/contracts/
test/unit/infrastructure/ai/
test/unit/infrastructure/contracts/
test/unit/infrastructure/vision/seal/
test/unit/application/agent/
test/unit/presentation/cli/
```

### `manual/`

放人工运行的调试脚本、真实 OCR 链路、真实 AI 链路、真实 API 客户端、PDF 转图片等耗时或依赖外部环境的脚本。

规范：

- 文件名不要使用 `test_*.py`，避免被 pytest 自动收集。
- 可以依赖 `test/testfiles/` 或 `test/fixtures/`。
- 默认输出写到 `test/output/`。
- 脚本入口使用 `if __name__ == "__main__":`。

示例：

```text
test/manual/documents/linearizer_pipeline.py
test/manual/documents/pdf2ocrjson_pipeline.py
test/manual/api/check_basic_info_client.py
test/manual/vision/seal_detector.py
```

### `fixtures/`

放小型、稳定、可复用、适合提交到仓库的测试样例。

适合放入 `fixtures/` 的内容：

- 小型 OCR 样例图片。
- 小型印章样例图片。
- 线性化文本样例。
- 小型参考输出文件。

不适合放入 `fixtures/` 的内容：

- 大 PDF、大批量扫描图片。
- 临时生成的 OCR 输出。
- 每次运行都会变化的日志、截图、裁剪图。
- 含敏感合同信息且未脱敏的真实材料。

当前结构：

```text
test/fixtures/linearized/
test/fixtures/ocr/
test/fixtures/seal/
test/fixtures/seal_expected/
```

### `testfiles/`

放本地调试使用的大文件样例，例如完整合同 PDF、批量合同图片、模拟篡改样本等。该目录当前由 `.gitignore` 忽略，不应作为 CI 或普通单元测试的必需输入。

如果某个单元测试必须依赖样例文件，应优先把最小化后的样例放到 `fixtures/`。

### `output/`

放人工脚本和调试过程产生的临时输出，例如 OCR JSON、PDF 渲染图片、线性化结果、印章裁剪图。该目录当前由 `.gitignore` 忽略。

单元测试不要依赖 `output/` 中的文件。

## 新增测试规则

1. 纯函数、模型转换、字段归一化、JSON 解析、工具适配器等稳定逻辑，放到 `test/unit/`。
2. 需要真实模型、真实 OCR、真实网页搜索、真实 API 服务或大文件输入的脚本，放到 `test/manual/`。
3. 共享输入样例先判断大小和稳定性：小而稳定放 `fixtures/`，大文件放 `testfiles/`。
4. 生成结果不要提交到 `unit/` 或 `fixtures/`，除非它是稳定的最小参考结果。
5. 新增测试不要导入旧兼容路径，应使用当前项目分层路径，例如：

```python
from core.domain.contracts.normalize import normalize_date
from core.infrastructure.text import linearize_ocr_page
from core.application.contracts import check_basic_info
```

## 运行方式

运行全部自动测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

只运行单元测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q test/unit
```

人工脚本按需单独运行，例如：

```powershell
.\.venv\Scripts\python.exe test\manual\documents\linearizer_pipeline.py
```

## 维护要求

- 保持 `pytest -q` 不收集 `manual/` 下的脚本。
- 保持 `unit/` 测试可离线运行。
- 不提交 `__pycache__/`、`.pytest_cache/`、`test/output/` 和大文件样例。
- 涉及真实合同材料时，提交前必须脱敏或改用模拟样例。
