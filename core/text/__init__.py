"""文本解析与结构化处理模块。"""

from .ocr2json import parse_file_to_json, parse_folder_to_json_list, parse_path_to_json_list

__all__ = ["parse_file_to_json", "parse_folder_to_json_list", "parse_path_to_json_list"]
