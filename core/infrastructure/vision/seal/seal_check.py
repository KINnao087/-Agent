from __future__ import annotations

import json
from pathlib import Path

from core.infrastructure.ai import parse_json_object, run_image_and_get_reply
from core.infrastructure.ai.logger import get_logger

from .detector import detect_seal_candidates
from .models import SealCandidate

logger = get_logger("seal-check")


def _get_image_paths(image_file_path: str | Path) -> list[Path]:
    image_file_path = Path(image_file_path)
    if not image_file_path.exists():
        raise FileNotFoundError(f"path not found: {image_file_path}")
    if not image_file_path.is_dir():
        raise NotADirectoryError(f"path is not a directory: {image_file_path}")

    image_suffixes = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    return sorted(
        path for path in image_file_path.iterdir()
        if path.is_file() and path.suffix.lower() in image_suffixes
    )


def _build_single_page_seal_check_message(
    image_path: str | Path,
    seal_candidates: list[SealCandidate],
) -> str:
    candidate_lines = "\n".join(
        f"- candidate_index: {index}, target_bbox: {candidate.bbox}"
        for index, candidate in enumerate(seal_candidates)
    )

    return f"""
你将收到一张合同整页图片。请直接观察整张图片，并只对下面列出的红色签章候选框逐个进行判断。

页面信息：
- image_path: {image_path}

候选框列表：
{candidate_lines}

规则：
1. target_bbox 的格式为 [x, y, width, height]。
2. 你必须按 candidate_index 逐个返回结果。
3. 不要把同一页里其他更显眼的印章当成当前候选框的结果。
4. owner 只能返回 seller、buyer 或 unknown。
5. owner 映射规则必须严格遵守：
   - buyer = 甲方 / 委托方 / 买方
   - seller = 乙方 / 受托方 / 卖方
6. 如果你判断某个候选框是甲方公章，则 owner 必须返回 buyer。
7. 如果你判断某个候选框是乙方公章，则 owner 必须返回 seller。
8. reason、owner、visible_company_name 三者必须保持一致，不能出现 owner=buyer 但 reason 写成“乙方公章”这类冲突。
9. visible_company_name 必须填写你从印章文字中直接识别出的公司名称；如果无法可靠识别则返回空字符串。
10. 如果某个候选框区域没有明确有效签章，请返回 present=false 或 null，并在 status 中优先返回 missing 或 unknown。
11. 如果无法可靠判断，请返回 unknown 或 null，不要臆造。
12. 只返回单个 JSON 对象，不要输出解释文字、代码块或 Markdown。

返回结构必须严格如下：
{{
  "candidate_reviews": [
    {{
      "candidate_index": 0,
      "present": true | false | null,
      "owner": "seller | buyer | unknown",
      "status": "intact | damaged | unclear | missing | unknown",
      "readable": true | false | null,
      "visible_company_name": "",
      "reason": ""
    }}
  ]
}}

补充要求：
1. 如果同一页出现两个主签章，通常分别对应甲方和乙方；不要随意把两个章都标成 buyer 或都标成 seller。
2. 如果候选框里是清晰完整的红色公章，status 优先返回 intact。
3. 如果章存在但模糊、残缺、被遮挡，可返回 damaged 或 unclear。
4. 如果 present=true，但无法判断归属，则 owner 返回 unknown。
""".strip()


def _check_single_page_seals(
    image_path: str | Path,
    seal_candidates: list[SealCandidate],
) -> dict[str, object]:
    """把单页图片和候选框发给多模态模型，并返回结构化审核结果。"""
    if not seal_candidates:
        return {"candidate_reviews": []}

    reply_text = run_image_and_get_reply(
        image_path=image_path,
        user_message=_build_single_page_seal_check_message(image_path, seal_candidates),
        work_description="你是科技合同红色签章审核助手，必须直接观察整页图片，并根据给定候选框逐个返回 JSON 结果。",
    )
    logger.info("单页签章审核 AI 返回：{}", reply_text)

    try:
        return parse_json_object(reply_text)
    except Exception as exc:
        logger.warning("解析单页签章审核结果失败: {}", exc)
        return {
            "candidate_reviews": [],
            "raw_reply": reply_text,
            "error": f"{type(exc).__name__}: {exc}",
        }


def check_contract_seals(input_path: str | Path) -> dict[str, str]:
    """接收合同图片文件夹路径，执行红色签章检测，并返回结构化 JSON。"""
    image_paths = _get_image_paths(input_path)
    page_results: list[dict[str, object]] = []
    seal_page_paths: list[str] = []

    for page_index, image_path in enumerate(image_paths, start=1):
        candidates = detect_seal_candidates(image_path=image_path, page_index=page_index)
        if candidates:
            seal_page_paths.append(str(image_path))
            review = _check_single_page_seals(image_path=image_path, seal_candidates=candidates)
        else:
            review = {"candidate_reviews": []}

        page_results.append(
            {
                "page_index": page_index,
                "image_path": str(image_path),
                "candidate_count": len(candidates),
                "review": review,
            }
        )

    payload = {
        "input_path": str(Path(input_path)),
        "seal_page_paths": seal_page_paths,
        "page_results": page_results,
    }
    return {
        "ok": True,
        "output": json.dumps(payload, ensure_ascii=False, indent=2),
    }
