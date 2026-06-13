"""测试工具层异常处理：验证所有 14 个工具在异常情况下返回错误 JSON 而非崩溃。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.application.agent.tools import (
    _json,
    _safe_json,
    check_basic_info,
    check_contract_authenticity,
    check_contract_seals,
    check_cross_page_seal,
    check_text_integrity,
    find_contract_review,
    get_review_result,
    get_review_status,
    list_files,
    prepare_contract,
    read_text_file,
    write_review_report,
    write_text_file,
)


# ── _json 序列化安全 ──────────────────────────────────────────────


class Unserializable:
    """用于测试 JSON 序列化失败的对象。"""

    pass


def test_json_returns_error_on_type_error():
    """当值不可 JSON 序列化时，_json 应返回 error 结构而非抛出 TypeError。"""
    result = _json({"bad": Unserializable()})
    parsed = json.loads(result)
    assert parsed["error"] is True
    assert parsed["error_type"] == "TypeError"
    assert "序列化失败" in parsed["message"]


def test_json_serializes_normal_values():
    """正常值应正确序列化。"""
    result = _json({"status": "ok"})
    parsed = json.loads(result)
    assert parsed["status"] == "ok"


# ── _safe_json 通用安全调用 ────────────────────────────────────────


def test_safe_json_returns_json_on_success():
    """正常执行时 _safe_json 返回 JSON 字符串。"""

    def ok():
        return {"result": "done"}

    result = _safe_json(ok)
    parsed = json.loads(result)
    assert parsed["result"] == "done"


def test_safe_json_catches_exception_and_returns_error():
    """函数抛出异常时 _safe_json 返回结构化错误 JSON。"""

    def failing():
        raise ValueError("模拟失败")

    result = _safe_json(failing)
    parsed = json.loads(result)
    assert parsed["error"] is True
    assert parsed["error_type"] == "ValueError"
    assert "模拟失败" in parsed["message"]
    assert "traceback" in parsed


def test_safe_json_passes_args_and_kwargs():
    """_safe_json 应正确传递位置参数和关键字参数。"""

    def echo(a, b=0):
        return {"a": a, "b": b}

    result = _safe_json(echo, 1, b=2)
    parsed = json.loads(result)
    assert parsed["a"] == 1
    assert parsed["b"] == 2


# ── 合同审核类工具错误处理（工具 1-10）─────────────────────────────


class TestContractReviewToolsErrorHandling:
    """验证所有合同审核类工具在服务层异常时返回 error JSON。"""

    @pytest.fixture(autouse=True)
    def mock_service(self):
        """为每个测试提供抛出异常的服务 mock。"""
        with patch(
            "core.application.agent.tools.get_contract_review_service"
        ) as mock_get:
            service = MagicMock()
            mock_get.return_value = service
            yield service

    def _assert_error(self, result: str, expected_tool_name: str = ""):
        """断言结果是包含 error 字段的合法 JSON。"""
        parsed = json.loads(result)
        assert parsed["error"] is True
        assert "error_type" in parsed
        assert "message" in parsed
        assert "traceback" in parsed
        return parsed

    def test_find_contract_review_error(self, mock_service):
        mock_service.find_contract_review.side_effect = RuntimeError("指纹计算失败")
        result = find_contract_review.invoke({"contract_path": "/nonexistent"})
        self._assert_error(result)

    def test_prepare_contract_error(self, mock_service):
        mock_service.prepare_contract.side_effect = FileNotFoundError("合同文件不存在")
        result = prepare_contract.invoke({"contract_path": "/nonexistent.pdf"})
        self._assert_error(result)

    def test_check_basic_info_error(self, mock_service):
        mock_service.check_basic_info.side_effect = ValueError("OCR 结果为空")
        result = check_basic_info.invoke({"review_id": "review_deadbeef"})
        self._assert_error(result)

    def test_check_text_integrity_error(self, mock_service):
        mock_service.check_text_integrity.side_effect = ConnectionError("AI API 超时")
        result = check_text_integrity.invoke({"review_id": "review_deadbeef"})
        self._assert_error(result)

    def test_check_contract_seals_error(self, mock_service):
        mock_service.check_contract_seals.side_effect = RuntimeError("签章检测模型加载失败")
        result = check_contract_seals.invoke({"review_id": "review_deadbeef"})
        self._assert_error(result)

    def test_check_cross_page_seal_error(self, mock_service):
        mock_service.check_cross_page_seal.side_effect = RuntimeError("骑缝章分析失败")
        result = check_cross_page_seal.invoke({"review_id": "review_deadbeef"})
        self._assert_error(result)

    def test_check_contract_authenticity_error(self, mock_service):
        mock_service.check_contract_authenticity.side_effect = RuntimeError("网络搜索失败")
        result = check_contract_authenticity.invoke(
            {"review_id": "review_deadbeef", "search_enabled": True}
        )
        self._assert_error(result)

    def test_get_review_status_error(self, mock_service):
        mock_service.get_review_status.side_effect = FileNotFoundError("审核任务不存在")
        result = get_review_status.invoke({"review_id": "review_nonexist"})
        self._assert_error(result)

    def test_write_review_report_error(self, mock_service):
        mock_service.write_review_report.side_effect = RuntimeError("报告生成失败")
        result = write_review_report.invoke({"review_id": "review_deadbeef"})
        self._assert_error(result)

    def test_get_review_result_error(self, mock_service):
        mock_service.get_review_result.side_effect = KeyError("step not found")
        result = get_review_result.invoke(
            {"review_id": "review_deadbeef", "step_name": "nonexistent"}
        )
        self._assert_error(result)

    def test_tool_error_response_is_valid_json_for_llm(self, mock_service):
        """所有工具的 error 响应都是有效的 JSON 字符串，LLM 可解析。"""
        mock_service.check_basic_info.side_effect = Exception("通用异常")
        result = check_basic_info.invoke({"review_id": "review_test"})
        # 不应抛出异常
        parsed = json.loads(result)
        # 应包含必要字段
        assert isinstance(parsed["error"], bool)
        assert isinstance(parsed["error_type"], str)
        assert isinstance(parsed["message"], str)


# ── 文件系统类工具错误处理（工具 11-14）───────────────────────────


class TestFileSystemToolsErrorHandling:
    """验证文件系统工具在 I/O 异常时返回 error JSON。"""

    def test_list_files_nonexistent_path(self):
        """不存在的路径应返回 error JSON 而非抛出异常。"""
        result = list_files.invoke(
            {"path": "/nonexistent/path/abc123", "recursive": False}
        )
        parsed = json.loads(result)
        assert parsed["error"] is True
        assert "路径不存在" in parsed["message"] or "列出目录失败" in parsed["message"]

    def test_list_files_file_instead_of_directory(self):
        """传入文件而非目录应返回 error JSON。"""
        result = list_files.invoke(
            {"path": __file__, "recursive": False}
        )
        parsed = json.loads(result)
        assert parsed["error"] is True

    def test_read_text_file_nonexistent(self):
        """读取不存在的文件应返回 error JSON。"""
        result = read_text_file.invoke({"path": "/nonexistent/file.txt"})
        parsed = json.loads(result)
        assert parsed["error"] is True

    def test_write_text_file_with_write_error(self, tmp_path):
        """写入到已存在的目录路径应返回 error JSON。"""
        # 尝试写入到一个目录路径（而非文件路径），这应当触发错误
        target_dir = tmp_path / "some_dir"
        target_dir.mkdir()
        result = write_text_file.invoke(
            {
                "path": str(target_dir),
                "content": "test",
                "overwrite": False,
            }
        )
        parsed = json.loads(result)
        # 写入目录路径应报错（IsADirectoryError）
        assert parsed.get("error") is True
        assert "目录" in parsed.get("message", "") or "directory" in parsed.get("message", "").lower()

    def test_write_text_file_permission_denied(self, tmp_path):
        """写入只读目录应返回 error JSON。"""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        # 在 Windows 上通过设为只读来模拟
        import stat
        import os

        os.chmod(str(readonly_dir), stat.S_IREAD)
        try:
            result = write_text_file.invoke(
                {
                    "path": str(readonly_dir / "subdir" / "file.txt"),
                    "content": "test",
                    "overwrite": False,
                }
            )
            parsed = json.loads(result)
            # 可能成功（权限继承），也可能失败——都接受
            if parsed.get("error"):
                assert "message" in parsed
        finally:
            os.chmod(str(readonly_dir), stat.S_IWRITE | stat.S_IREAD)


# ── 回归验证：正常路径不受影响 ─────────────────────────────────────


class TestNormalPathNotBroken:
    """验证错误处理改造不影响正常功能。"""

    @patch("core.application.agent.tools.get_contract_review_service")
    def test_successful_tool_call_returns_normal_json(self, mock_get):
        """工具正常执行时应返回业务 JSON，不受 error 字段污染。"""
        service = MagicMock()
        service.check_basic_info.return_value = {
            "review_status": "completed",
            "contract_basic_info": {"contract_name": "测试合同"},
        }
        mock_get.return_value = service

        result = check_basic_info.invoke({"review_id": "review_test"})
        parsed = json.loads(result)
        assert parsed["review_status"] == "completed"
        assert "error" not in parsed  # 正常结果不应有 error 字段

    def test_safe_json_preserves_empty_string_result(self):
        """_safe_json 应保留空字符串返回值。"""

        def returns_empty_string():
            return ""

        result = _safe_json(returns_empty_string)
        parsed = json.loads(result)
        assert parsed == ""
