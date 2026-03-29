from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib import error, request


DEFAULT_API_URL = "http://127.0.0.1:8000/api/contracts/check-basic-info"
DEFAULT_CONTRACT_TEXT_PATH = Path(__file__).resolve().parent / "output" / "contract_linearized.txt"


def build_default_platform_basic_info() -> dict:
    """构造一份可直接发请求的示例 platform_basic_info。"""
    return {
        "contract_no": "",
        "project_name": "小动物PET时间符合电子学研制",
        "sign_date": "2025年5月",
        "contract_period": "2025年5月10日至2029年5月9日",
        "transaction_amount": "49万元",
        "technology_transaction_amount": "",
        "payment_mode": "分期支付",
        "seller": {
            "name": "中国科学技术大学",
            "project_leader": "曹喆",
            "legal_representative": "常进",
            "legal_phone": "13515646364",
            "address": "安徽省合肥市包河区金寨路96号",
            "agent": "曹喆",
            "agent_phone": "13515646364",
        },
        "buyer": {
            "name": "深圳先进技术研究院",
            "legal_representative": "刘陈立",
            "legal_phone": "15818518712",
            "address": "深圳市南山区西丽深圳大学城学苑大道1068号",
            "agent": "胡战列",
            "agent_phone": "15818518712",
        },
    }


def load_platform_basic_info(platform_json_path: str | None) -> dict:
    """读取平台侧基础信息；未提供时使用内置示例。"""
    if not platform_json_path:
        return build_default_platform_basic_info()

    path = Path(platform_json_path)
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(contract_text_path: str | Path, platform_json_path: str | None) -> dict:
    """构造发给 /api/contracts/check-basic-info 的请求体。"""
    contract_text = Path(contract_text_path).read_text(encoding="utf-8")
    platform_basic_info = load_platform_basic_info(platform_json_path)
    return {
        "contract_text": contract_text,
        "platform_basic_info": platform_basic_info,
    }


def send_request(api_url: str, payload: dict) -> dict:
    """向 API 发送请求并返回 JSON 响应。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        api_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect_unmatched_fields(compare_result: dict, prefix: str = "") -> list[dict]:
    """递归收集 compare_result 中未匹配的字段。"""
    unmatched_fields: list[dict] = []

    for key, value in compare_result.items():
        path = f"{prefix}.{key}" if prefix else key
        if not isinstance(value, dict):
            continue

        if "status" in value:
            status = value.get("status", "")
            if status != "match":
                unmatched_fields.append(
                    {
                        "path": path,
                        "label": value.get("label", ""),
                        "status": status,
                        "contract_value": value.get("contract_value", ""),
                        "platform_value": value.get("platform_value", ""),
                    }
                )
            continue

        unmatched_fields.extend(collect_unmatched_fields(value, path))

    return unmatched_fields


def print_unmatched_fields(response: dict) -> None:
    """打印 compare_result 中未匹配的字段。"""
    unmatched_fields = collect_unmatched_fields(response.get("compare_result", {}))
    if not unmatched_fields:
        print("All compared fields matched.")
        return

    print("Unmatched fields:")
    for item in unmatched_fields:
        print(
            f"- {item['path']} | {item['label']} | status={item['status']} | "
            f"contract={item['contract_value']} | platform={item['platform_value']}"
        )


def build_parser() -> argparse.ArgumentParser:
    """构造用户端测试脚本的命令行参数。"""
    parser = argparse.ArgumentParser(description="向合同基础信息核对 API 发送请求并打印 summary。")
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"API 地址，默认 {DEFAULT_API_URL}",
    )
    parser.add_argument(
        "--contract-text",
        default=str(DEFAULT_CONTRACT_TEXT_PATH),
        help="合同线性化文本路径，默认使用 test/output/contract_linearized.txt",
    )
    parser.add_argument(
        "--platform-json",
        help="可选，平台侧 basic info JSON 文件路径；未提供时使用内置示例。",
    )
    return parser


def main() -> int:
    """读取本地测试数据，调用 API，并打印 summary。"""
    parser = build_parser()
    args = parser.parse_args()

    payload = build_payload(args.contract_text, args.platform_json)

    try:
        response = send_request(args.url, payload)
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}")
        print(error_text)
        return 1
    except error.URLError as exc:
        print(f"Request failed: {exc}")
        return 1

    summary = response.get("summary", {})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print_unmatched_fields(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
