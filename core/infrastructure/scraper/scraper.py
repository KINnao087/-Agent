import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

import tls_client

from dotenv import load_dotenv
from tls_client.response import Response as TLSResponse

load_dotenv()


HOME_URL = "https://www.qcc.com/"
SEARCH_PAGE_URL = HOME_URL
SEARCH_API_REQUEST_PATH = "/api/batch/getBatchFollowKeyNo"
SEARCH_API_SIGN_PATH = SEARCH_API_REQUEST_PATH.lower()
SEARCH_API_URL = f"https://www.qcc.com{SEARCH_API_REQUEST_PATH}"
SEARCH_COMPANY_URL = "https://www.qcc.com/firm/"

COMPANY_DETAIL_API_REQUEST_PATH = "/api/company/getDetail"
COMPANY_LOCATION_API_REQUEST_PATH = "/api/company/getLocation"
COMPANY_INDUSTRY_API_REQUEST_PATH = "/api/customDetail/getIndustry"
COMPANY_PHONE_API_REQUEST_PATH = "/api/customDetail/getPhone"
COMPANY_EMPLOYEE_API_REQUEST_PATH = "/api/company/getEmployeeList"
ZONE_PARK_DETAIL_API_REQUEST_PATH = "/api/more/getZoneParkDetail"
ZONE_PARK_COMPANY_DETAIL_API_REQUEST_PATH = "/api/more/getZoneParkCompanyDetail"

SCRAPER_DIR = Path(__file__).resolve().parent
KEY_JS_PATH = SCRAPER_DIR / "key.js"
VALUE_JS_PATH = SCRAPER_DIR / "value.js"

ACW_SC_V2_XOR_KEY = "3000176000856006061501533003690027800375"
ACW_SC_V2_PERMUTATION = [
    0xF,
    0x23,
    0x1D,
    0x18,
    0x21,
    0x10,
    0x1,
    0x26,
    0xA,
    0x9,
    0x13,
    0x1F,
    0x28,
    0x1B,
    0x16,
    0x17,
    0x19,
    0xD,
    0x6,
    0xB,
    0x27,
    0x12,
    0x14,
    0x8,
    0xE,
    0x15,
    0x20,
    0x1A,
    0x2,
    0x1E,
    0x7,
    0x4,
    0x11,
    0x5,
    0x3,
    0x1C,
    0x22,
    0x25,
    0xC,
    0x24,
]
ACW_ARG1_RE = re.compile(r"arg1='([0-9a-fA-F]+)'")
PID_TID_RE = re.compile(r"window\.pid='([^']+)';\s*window\.tid='([^']+)'")
LOGIN_REQUIRED_MESSAGE = "使用该功能需要用户登录"
TLS_CLIENT_IDENTIFIER = "chrome_120"

DEFAULT_HEADERS = {
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


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """把浏览器 Cookie 请求头拆成当前 session 可用的键值字典。"""
    cookies: dict[str, str] = {}
    for item in str(cookie_header or "").split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value
    return cookies


def _new_session() -> tls_client.Session:
    """创建一个模拟 Chrome TLS 指纹的 session。"""
    return tls_client.Session(
        client_identifier=TLS_CLIENT_IDENTIFIER,
        random_tls_extension_order=True,
    )


def _session_request(
    session: tls_client.Session,
    method: str,
    url: str,
    **kwargs: Any,
) -> TLSResponse:
    """把 requests 风格参数转换成 tls_client 请求。"""
    timeout = kwargs.pop("timeout", None)
    if timeout is not None:
        kwargs["timeout_seconds"] = timeout
    kwargs.setdefault("allow_redirects", True)
    return session.execute_request(method=method.upper(), url=url, **kwargs)


def _raise_for_status(response: TLSResponse) -> None:
    """为 tls_client 响应补一个基础状态码检查。"""
    status_code = int(response.status_code or 0)
    if 400 <= status_code:
        raise RuntimeError(f"HTTP {status_code} for {response.url}: {response.text[:300]}")


def _attach_login_cookie(session: tls_client.Session, cookie_header: str | None = None) -> None:
    """把用户提供的登录态 Cookie 挂到当前 session。"""
    cookie_text = (cookie_header or os.environ.get("QCC_COOKIE") or "").strip()
    if not cookie_text:
        return
    for key, value in _parse_cookie_header(cookie_text).items():
        session.cookies.set(key, value)


def _unscramble_acw_arg1(arg1: str) -> str:
    """按阿里云 WAF 的固定置换表还原 arg1。"""
    restored = [""] * len(ACW_SC_V2_PERMUTATION)
    for index, char in enumerate(arg1):
        for target_index, position in enumerate(ACW_SC_V2_PERMUTATION):
            if position == index + 1:
                restored[target_index] = char
                break
    return "".join(restored)


def _hex_xor(left: str, right: str) -> str:
    """对两个十六进制串按字节异或。"""
    return "".join(
        f"{int(left[i : i + 2], 16) ^ int(right[i : i + 2], 16):02x}"
        for i in range(0, min(len(left), len(right)), 2)
    )


def _solve_acw_sc_v2_from_html(html: str) -> str | None:
    """从挑战页 HTML 计算出 acw_sc__v2 Cookie。"""
    match = ACW_ARG1_RE.search(html)
    if not match:
        return None
    return _hex_xor(_unscramble_acw_arg1(match.group(1)), ACW_SC_V2_XOR_KEY)


def _request_with_waf_retry(
    session: tls_client.Session,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> TLSResponse:
    """若命中 acw_sc__v2 挑战，自动补 Cookie 后重试同一个请求。"""
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    response = _session_request(session, method, url, headers=request_headers, timeout=15, **kwargs)

    solved_cookie = _solve_acw_sc_v2_from_html(response.text)
    if solved_cookie:
        session.cookies.set("acw_sc__v2", solved_cookie)
        response = _session_request(session, method, url, headers=request_headers, timeout=15, **kwargs)

    return response


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
    match = PID_TID_RE.search(html)
    if not match:
        raise ValueError("Failed to extract pid/tid from qcc homepage.")

    pid, tid = match.groups()
    return pid.lower(), tid.lower()


def _fetch_pid_tid(
    session: tls_client.Session | None = None,
    cookie_header: str | None = None,
) -> tuple[str, str]:
    """请求首页，并返回当前会话绑定的 pid 和 tid。"""
    owns_session = session is None
    client = session or _new_session()
    try:
        _attach_login_cookie(client, cookie_header)
        response = _request_with_waf_retry(client, "GET", HOME_URL)
        _raise_for_status(response)
        return _extract_pid_tid(response.text)
    finally:
        if owns_session:
            client.close()


def _get_key(path: str, payload: str = "{}") -> str:
    """通过调用 key.js 计算动态请求头的 key。"""
    return _run_js(KEY_JS_PATH, _normalize_sign_path(path), payload)


def _get_value(path: str, payload: str = "{}", tid: str | None = None) -> str:
    """通过调用 value.js 计算动态请求头的 value。"""
    actual_tid = str(tid).lower() if tid else _fetch_pid_tid()[1]
    return _run_js(VALUE_JS_PATH, _normalize_sign_path(path), payload, actual_tid)


def _raise_for_auth_error(response: TLSResponse) -> None:
    """把企查查的登录态拦截响应转换成显式异常。"""
    try:
        data = response.json()
    except ValueError:
        return
    if response.status_code == 209 and data.get("status") == 409:
        message = data.get("message") or LOGIN_REQUIRED_MESSAGE
        raise PermissionError(
            f"{message}。请先在环境变量 QCC_COOKIE 中提供浏览器登录态 Cookie。"
        )


def _request_company_api(
    method: str,
    path: str,
    *,
    keyno: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    cookie_header: str | None = None,
    session: tls_client.Session | None = None,
) -> dict[str, Any]:
    """统一发起企查查公司详情相关 API 请求。"""
    owns_session = session is None
    client = session or _new_session()
    try:
        _attach_login_cookie(client, cookie_header)
        pid, _ = _fetch_pid_tid(client, cookie_header)
        referer = f"{SEARCH_COMPANY_URL}{keyno}.html" if keyno else HOME_URL
        request_headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "referer": referer,
            "x-pid": pid,
        }
        response = _session_request(
            client,
            method,
            f"https://www.qcc.com{path}",
            headers={**DEFAULT_HEADERS, **request_headers},
            params=params,
            json=json_body,
            timeout=15,
        )
        _raise_for_auth_error(response)
        _raise_for_status(response)
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected response payload from {path}: {data}")
        return data
    finally:
        if owns_session:
            client.close()


def get_company_key(company_name: str, cookie_header: str | None = None) -> str | None:
    """通过批量接口按公司名获取公司主体 KeyNo。"""
    payload = _build_payload({"names": [company_name]})

    with _new_session() as session:
        _attach_login_cookie(session, cookie_header)
        pid, tid = _fetch_pid_tid(session, cookie_header)
        header_key = _get_key(SEARCH_API_SIGN_PATH, payload)
        header_value = _get_value(SEARCH_API_SIGN_PATH, payload, tid)

        request_headers = {
            **DEFAULT_HEADERS,
            "content-type": "application/json",
            "referer": SEARCH_PAGE_URL,
            "x-pid": pid,
            header_key: header_value,
        }

        response = _session_request(
            session,
            "POST",
            SEARCH_API_URL,
            headers=request_headers,
            data=payload.encode("utf-8"),
            timeout=15,
        )
        _raise_for_auth_error(response)
        _raise_for_status(response)
        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response payload: {data}")

        if not data:
            return None

        return data[0].get("KeyNo")


def get_company_info(ckeyno: str, cookie_header: str | None = None) -> str:
    """根据公司 KeyNo 访问公司详情页并返回原始 HTML。"""
    with _new_session() as session:
        _attach_login_cookie(session, cookie_header)
        pid, _ = _fetch_pid_tid(session, cookie_header)
        request_headers = {
            **DEFAULT_HEADERS,
            "referer": HOME_URL,
            "x-pid": pid,
        }
        response = _request_with_waf_retry(
            session,
            "GET",
            f"{SEARCH_COMPANY_URL}{ckeyno}.html",
            headers=request_headers,
        )
        _raise_for_status(response)
        return response.text


def get_company_detail(keyno: str, cookie_header: str | None = None) -> dict[str, Any]:
    """首屏详情主接口，返回主体信息、标签、联系方式等聚合数据。"""
    return _request_company_api(
        "GET",
        COMPANY_DETAIL_API_REQUEST_PATH,
        keyno=keyno,
        params={"keyNo": keyno},
        cookie_header=cookie_header,
    )


def get_company_location(keyno: str, cookie_header: str | None = None) -> dict[str, Any]:
    """详情页地图接口，通常返回经纬度和地址定位信息。"""
    return _request_company_api(
        "GET",
        COMPANY_LOCATION_API_REQUEST_PATH,
        keyno=keyno,
        params={"keyNo": keyno},
        cookie_header=cookie_header,
    )


def get_company_industry_profile(keyno: str, cookie_header: str | None = None) -> dict[str, Any]:
    """行业规模弹窗接口，包含行业、规模、经营范围等补充信息。"""
    return _request_company_api(
        "POST",
        COMPANY_INDUSTRY_API_REQUEST_PATH,
        keyno=keyno,
        json_body={"keyNo": keyno},
        cookie_header=cookie_header,
    )


def get_company_phone_profile(
    keyno: str,
    from_page: str = "search",
    cookie_header: str | None = None,
) -> dict[str, Any]:
    """联系方式弹窗接口，包含 ContactInfo、历史电话和经办标签信息。"""
    return _request_company_api(
        "POST",
        COMPANY_PHONE_API_REQUEST_PATH,
        keyno=keyno,
        json_body={"keyNo": keyno, "from": from_page},
        cookie_header=cookie_header,
    )


def get_company_employee_list(keyno: str, cookie_header: str | None = None) -> dict[str, Any]:
    """人员选择接口，返回企业相关人员列表。"""
    return _request_company_api(
        "POST",
        COMPANY_EMPLOYEE_API_REQUEST_PATH,
        keyno=keyno,
        json_body={"keyNo": keyno},
        cookie_header=cookie_header,
    )


def get_zone_park_detail(params: dict[str, Any], cookie_header: str | None = None) -> dict[str, Any]:
    """园区详情接口，页面源码中用于高新区/园区相关页面。"""
    keyno = str(params.get("keyNo") or params.get("companyKeyNo") or "")
    return _request_company_api(
        "GET",
        ZONE_PARK_DETAIL_API_REQUEST_PATH,
        keyno=keyno,
        params=params,
        cookie_header=cookie_header,
    )


def get_zone_park_company_detail(
    params: dict[str, Any],
    cookie_header: str | None = None,
) -> dict[str, Any]:
    """园区企业详情接口，适合进一步验证是否属于某类园区。"""
    keyno = str(params.get("keyNo") or params.get("companyKeyNo") or "")
    return _request_company_api(
        "GET",
        ZONE_PARK_COMPANY_DETAIL_API_REQUEST_PATH,
        keyno=keyno,
        params=params,
        cookie_header=cookie_header,
    )


def get_company_snapshot(keyno: str, cookie_header: str | None = None) -> dict[str, Any]:
    """一次性拉取公司详情页最相关的几组接口数据。"""
    return {
        "detail": get_company_detail(keyno, cookie_header=cookie_header),
        "industry": get_company_industry_profile(keyno, cookie_header=cookie_header),
        "phone": get_company_phone_profile(keyno, cookie_header=cookie_header),
        "employees": get_company_employee_list(keyno, cookie_header=cookie_header),
        "location": get_company_location(keyno, cookie_header=cookie_header),
    }

from core.shared import format_json_output

def main() -> None:
    """本地手工调试入口。"""
    try:
        company_key = get_company_key("深圳市腾讯计算机系统有限公司")
        print(company_key)
        if company_key:
            print(get_company_employee_list(get_company_snapshot(company_key)))

    except PermissionError as exc:
        print(exc)


if __name__ == "__main__":
    main()
