from __future__ import annotations

from pathlib import Path


def resolve_path(path_value: str | Path) -> Path:
    """把输入路径规范化为绝对路径。"""
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def ensure_directory(path_value: str | Path) -> Path:
    """确保目录存在，并返回其绝对路径。"""
    path = resolve_path(path_value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent_dir(path_value: str | Path) -> Path:
    """确保文件的父目录存在，并返回文件绝对路径。"""
    path = resolve_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def list_files_by_suffix(directory: str | Path, *suffixes: str) -> list[Path]:
    """列出目录下指定后缀的文件，并按名称排序。"""
    path = resolve_path(directory)
    if not path.exists():
        raise FileNotFoundError(f"input folder not found: {path}")
    if not path.is_dir():
        raise ValueError(f"input path is not a directory: {path}")

    normalized_suffixes = {suffix.lower() for suffix in suffixes}
    return sorted(
        file_path
        for file_path in path.iterdir()
        if file_path.is_file() and file_path.suffix.lower() in normalized_suffixes
    )
