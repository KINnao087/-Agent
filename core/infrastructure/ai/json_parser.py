from __future__ import annotations

import json


def extract_json_text(response_text: str) -> str:
    """从模型回复中提取 JSON 文本。"""
    text = (response_text or "").strip()
    if not text:
        raise ValueError("model returned empty content")

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise ValueError("model response does not contain a JSON object")


def parse_json_object(response_text: str) -> dict:
    """把模型回复解析成 JSON 对象。"""
    data = json.loads(extract_json_text(response_text))
    if not isinstance(data, dict):
        raise ValueError("model response JSON must be an object")
    return data
