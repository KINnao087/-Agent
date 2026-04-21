from __future__ import annotations

from typing import Any

try:
    import tiktoken
except ImportError:
    tiktoken = None


_TOKEN_ENCODINGS: dict[str, object] = {}
_IMAGE_URL_TOKEN_BUDGET = 1024


def get_token_encoding(model: str):
    """获取并缓存指定模型对应的 tokenizer。"""
    if tiktoken is None:
        raise RuntimeError("tiktoken is not installed")

    encoding = _TOKEN_ENCODINGS.get(model)
    if encoding is not None:
        return encoding

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    _TOKEN_ENCODINGS[model] = encoding
    return encoding


def estimate_tokens(text: str, model: str) -> int:
    """使用 tiktoken 或回退规则估算文本 token 数。"""
    if not text:
        return 0

    try:
        encoding = get_token_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        english_chars = sum(1 for char in text if ord(char) < 128)
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        other_chars = len(text) - english_chars - chinese_chars
        tokens = english_chars / 4 + chinese_chars / 1.3 + other_chars / 4
        return max(1, int(tokens + 0.5))


def _estimate_content_tokens(content: Any, model: str) -> int:
    """Estimate tokens for string or OpenAI-style multimodal message content."""
    if not content:
        return 0

    if isinstance(content, str):
        return estimate_tokens(content, model)

    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text":
                    total += estimate_tokens(str(item.get("text", "")), model)
                    continue
                if item_type == "image_url":
                    total += _IMAGE_URL_TOKEN_BUDGET
                    continue
            total += estimate_tokens(str(item), model)
        return total

    if isinstance(content, dict):
        if content.get("type") == "image_url" or "image_url" in content:
            return _IMAGE_URL_TOKEN_BUDGET
        return estimate_tokens(str(content), model)

    return estimate_tokens(str(content), model)


def count_message_tokens(message: dict, model: str) -> int:
    """估算一条消息在对话中的 token 开销。"""
    tokens = 0

    if "role" in message:
        tokens += estimate_tokens(message["role"], model)

    if "content" in message and message["content"]:
        tokens += _estimate_content_tokens(message["content"], model)

    if "tool_calls" in message and message["tool_calls"]:
        for tool_call in message["tool_calls"]:
            function = tool_call.get("function")
            if not function:
                continue
            if "name" in function:
                tokens += estimate_tokens(function["name"], model)
            if "arguments" in function:
                tokens += estimate_tokens(function["arguments"], model)

    if "name" in message and "content" in message:
        tokens += estimate_tokens(message["name"], model)
        tokens += _estimate_content_tokens(message["content"], model)

    tokens += 10
    return tokens
