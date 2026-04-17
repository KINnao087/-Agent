import json
from typing import Any


def format_json_output(data: Any, indent: int = 2, sort_keys: bool = False) -> str:
    """
    将 Python 对象或 JSON 字符串格式化为漂亮的 JSON 字符串。

    :param data: dict / list / tuple / JSON字符串
    :param indent: 缩进空格数
    :param sort_keys: 是否按 key 排序
    :return: 格式化后的 JSON 字符串
    """
    # 如果传进来的是 JSON 字符串，先解析
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"输入的字符串不是合法 JSON: {e}") from e

    # 再格式化输出
    try:
        return json.dumps(
            data,
            ensure_ascii=False,  # 保留中文，不转 \uXXXX
            indent=indent,
            sort_keys=sort_keys
        )
    except TypeError as e:
        raise TypeError(f"输入对象无法序列化为 JSON: {e}") from e
