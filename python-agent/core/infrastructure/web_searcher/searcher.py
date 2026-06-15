from __future__ import annotations

import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


def tavily_search(q: str, sdepth: str = "advanced") -> dict:
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured")
        return TavilyClient(api_key=api_key).search(
            query=q,
            search_depth=sdepth,
        )
    except Exception as exc:
        raise RuntimeError(
            f"网络搜索失败 ({q[:50]}...): {type(exc).__name__}: {exc}"
        ) from exc
