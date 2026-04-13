import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote

import requests


HOME_URL = "https://www.qcc.com/"
SEARCH_PAGE_URL = HOME_URL
SEARCH_API_REQUEST_PATH = "/api/batch/getBatchFollowKeyNo"
SEARCH_API_SIGN_PATH = SEARCH_API_REQUEST_PATH.lower()
SEARCH_API_URL = f"https://www.qcc.com{SEARCH_API_REQUEST_PATH}"
SEARCH_COMPANY_URL = "https://www.qcc.com/firm/"
SCRAPER_DIR = Path(__file__).resolve().parent
KEY_JS_PATH = SCRAPER_DIR / "key.js"
VALUE_JS_PATH = SCRAPER_DIR / "value.js"

headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": HOME_URL,
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
    "cookie": (
        "QCCSESSID=c651dc4e17475ca24d53d4d7d8; "
        "qcc_did=16acbb1b-5082-4228-86a2-7208235171be; "
        "UM_distinctid=19d5726b3e474d-0ac2aa0dfa54c08-26061f51-1fa400-19d5726b3e52927; "
        "_c_WBKFRo=SsBUBJ90GtgVb3KgFE9Ltc1GV1c7TJVb9gKVIywT; "
        "acw_tc=76b20f8817760531739087262e72bf0e538ab4e942e1c0542902464628a910; "
        "CNZZDATA1254842228=559261268-1775283647-https%253A%252F%252Fwww.google.com%252F%7C1776053208"
    ),
}


def _str_to_utf8(s: str) -> str:
    """将中文关键词编码成 qcc URL 使用的小写 UTF-8 百分号转义字符串。"""
    return quote(s, safe="").lower()


def _build_payload(data: dict | list) -> str:
    """将请求体序列化成紧凑 JSON 字符串。"""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _normalize_sign_path(path: str) -> str:
    """将传给 JS 签名函数的路径统一转成小写。"""
    return str(path).lower()


def _run_js(script_path: Path, *args: str) -> str:
    """执行本地 Node 签名脚本，并返回去掉首尾空白后的输出。"""
    result = subprocess.run(
        ["node", str(script_path), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=SCRAPER_DIR,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "Unknown Node error."
        raise RuntimeError(f"Failed to run {script_path.name}: {stderr}")

    return result.stdout.strip()


def _extract_pid_tid(html: str) -> tuple[str, str]:
    """从 qcc 页面 HTML 中提取当前会话对应的 pid 和 tid。"""
    match = re.search(r"window\.pid='([^']+)';\s*window\.tid='([^']+)'", html)
    if not match:
        raise ValueError("Failed to extract pid/tid from qcc homepage.")

    pid, tid = match.groups()
    return pid.lower(), tid.lower()


def _fetch_pid_tid(session: requests.Session | None = None) -> tuple[str, str]:
    """请求首页，并返回当前会话绑定的 pid 和 tid。"""
    client = session or requests.Session()
    response = client.get(HOME_URL, headers=headers, timeout=15)
    response.raise_for_status()
    return _extract_pid_tid(response.text)


def _get_key(path: str, payload: str = "{}") -> str:
    """通过调用 key.js 计算动态请求头的 key。"""
    return _run_js(KEY_JS_PATH, _normalize_sign_path(path), payload)


def _get_value(path: str, payload: str = "{}", tid: str | None = None) -> str:
    """通过调用 value.js 计算动态请求头的 value。"""
    actual_tid = str(tid).lower() if tid else _fetch_pid_tid()[1]
    return _run_js(VALUE_JS_PATH, _normalize_sign_path(path), payload, actual_tid)


def get_company_key(company_name: str) -> str | None:
    """通过批量接口按公司名获取公司主体 KeyNo。"""
    payload = _build_payload({"names": [company_name]})

    with requests.Session() as session:
        pid, tid = _fetch_pid_tid(session)
        header_key = _get_key(SEARCH_API_SIGN_PATH, payload)
        header_value = _get_value(SEARCH_API_SIGN_PATH, payload, tid)

        request_headers = {
            **headers,
            "content-type": "application/json",
            "referer": SEARCH_PAGE_URL,
            "x-pid": pid,
            header_key: header_value,
        }

        response = session.post(
            SEARCH_API_URL,
            headers=request_headers,
            data=payload.encode("utf-8"),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response payload: {data}")

        if not data:
            return None

        return data[0].get("KeyNo")


def get_company_info(ckeyno: str) -> str:
    """根据公司 KeyNo 访问公司详情页并返回原始 HTML。"""
    with requests.Session() as session:
        pid, _ = _fetch_pid_tid(session)
        request_headers = {
            **headers,
            "referer": HOME_URL,
            "x-pid": pid,
        }
        response = session.get(
            url=f"{SEARCH_COMPANY_URL}{ckeyno}.html",
            headers=request_headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.text


def main() -> None:
    """本地手工调试入口。"""
    company_key = get_company_key("深圳市腾讯计算机系统有限公司")
    print(company_key)
    if company_key:
        print(get_company_info(company_key)[:500])


if __name__ == "__main__":
    main()
