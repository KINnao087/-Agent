from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any


def _resolve_path(path: str | Path | None = None) -> Path:
    """Resolve a user supplied path without requiring it to already exist."""
    value = "." if path is None or str(path).strip() == "" else str(path).strip()
    return Path(value).expanduser().resolve(strict=False)


def ls(
    path: str | Path = ".",
    recursive: bool = False,
    max_entries: int = 200,
    include_hidden: bool = True,
) -> dict[str, Any]:
    """List files and directories under a path."""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"path does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"path is not a directory: {target}")

    entry_iter = target.rglob("*") if recursive else target.iterdir()
    entries: list[dict[str, Any]] = []
    skipped = 0

    for entry in sorted(entry_iter, key=lambda item: str(item).lower()):
        if not include_hidden and entry.name.startswith("."):
            continue
        if len(entries) >= max_entries:
            skipped += 1
            continue

        try:
            stat = entry.stat()
        except OSError:
            size = None
            modified = None
        else:
            size = stat.st_size
            modified = stat.st_mtime

        entries.append(
            {
                "name": entry.name,
                "path": str(entry),
                "relative_path": str(entry.relative_to(target)),
                "type": "directory" if entry.is_dir() else "file",
                "size": size,
                "modified": modified,
            }
        )

    return {
        "path": str(target),
        "recursive": recursive,
        "entries": entries,
        "entry_count": len(entries),
        "skipped_count": skipped,
    }


def readfile(
    path: str | Path,
    encoding: str = "utf-8",
    max_chars: int = 20000,
) -> dict[str, Any]:
    """Read a text file and return its content."""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"file does not exist: {target}")
    if not target.is_file():
        raise IsADirectoryError(f"path is not a file: {target}")

    text = target.read_text(encoding=encoding, errors="replace")
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "path": str(target),
        "encoding": encoding,
        "content": text,
        "char_count": len(text),
        "size": target.stat().st_size,
        "truncated": truncated,
        "max_chars": max_chars,
    }


def readimage(
    path: str | Path,
    max_bytes: int = 6_000_000,
    include_data_url: bool = True,
) -> dict[str, Any]:
    """Read an image file and return base64-encoded image data."""
    target = _resolve_path(path)
    if not target.exists():
        raise FileNotFoundError(f"image file does not exist: {target}")
    if not target.is_file():
        raise IsADirectoryError(f"path is not a file: {target}")

    suffix = target.suffix.lower()
    supported_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    if suffix not in supported_suffixes:
        raise ValueError(f"unsupported image suffix: {suffix}")

    size = target.stat().st_size
    if size > max_bytes:
        raise ValueError(f"image file is too large: {size} bytes > max_bytes={max_bytes}")

    image_bytes = target.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    data_url = f"data:{mime_type};base64,{image_base64}" if include_data_url else ""

    return {
        "path": str(target),
        "name": target.name,
        "mime_type": mime_type,
        "size": size,
        "base64": image_base64,
        "data_url": data_url,
    }


def writefile(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = False,
    create_parents: bool = True,
) -> dict[str, Any]:
    """Write text content to a file."""
    target = _resolve_path(path)
    existed_before = target.exists()
    if existed_before and target.is_dir():
        raise IsADirectoryError(f"path is a directory: {target}")
    if existed_before and not overwrite:
        raise FileExistsError(f"file already exists, pass overwrite=true to replace it: {target}")

    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.exists():
        raise FileNotFoundError(f"parent directory does not exist: {target.parent}")

    text = "" if content is None else str(content)
    target.write_text(text, encoding=encoding)
    return {
        "path": str(target),
        "encoding": encoding,
        "char_count": len(text),
        "size": target.stat().st_size,
        "overwritten": existed_before,
    }
