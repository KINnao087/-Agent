from collections import Counter, defaultdict
from pathlib import Path

from core.domain.contracts import CPSealFragment, CPSealPageResult, CPSealResult, CPSealEdge
from core.shared.logging import get_logger
from core.infrastructure.vision.seal import SealBBox
from core.infrastructure.vision.seal.detector import find_red_contours, build_candidate_bbox
from core.infrastructure.vision.seal.preprocessing import load_image, build_red_mask, clean_red_mask

logger = get_logger("cross-page-seal-detector")

CPSEAL_MIN_CONTOUR_AREA = 10
CPSEAL_MAX_CONTOURS_PER_PAGE = 120


def _check_edge(box: SealBBox, imagew: int, imageh: int) -> CPSealEdge:
    """判断候选框靠近页面哪一条边。"""
    if imagew <= 0 or imageh <= 0:
        return "unknown"

    x, y, width, height = box
    if width <= 0 or height <= 0:
        return "unknown"

    distances = {
        "left": max(0, x),
        "right": max(0, imagew - (x + width)),
        "top": max(0, y),
        "bottom": max(0, imageh - (y + height)),
    }
    edge = min(distances, key=distances.get)

    edge_threshold = max(20, int(min(imagew, imageh) * 0.15))
    if distances[edge] > edge_threshold:
        return "unknown"
    return edge

def _count_red_pixels(box: SealBBox, red_mask) -> int:
    """统计 bbox 范围内的红色像素点数量。"""
    if red_mask is None:
        return 0

    imageh, imagew = red_mask.shape[:2]
    x, y, width, height = box
    if width <= 0 or height <= 0:
        return 0

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(imagew, x + width)
    y2 = min(imageh, y + height)
    if x1 >= x2 or y1 >= y2:
        return 0

    bbox_mask = red_mask[y1:y2, x1:x2]
    return int((bbox_mask > 0).sum())


def _score_fragment(box: SealBBox, edge: CPSealEdge, red_area: int) -> float:
    """给疑似骑缝章碎片一个简单候选分数。"""
    if edge == "unknown":
        return 0.0

    x, y, width, height = box
    if width <= 0 or height <= 0:
        return 0.0

    score = 0.0

    # 1. 靠边是骑缝章最重要特征
    score += 0.4

    # 2. 红色像素越多越可信
    if red_area >= 2000:
        score += 0.4
    elif red_area >= 1000:
        score += 0.3
    elif red_area >= 300:
        score += 0.2
    elif red_area >= 100:
        score += 0.1

    # 3. 骑缝章碎片通常是贴边的窄长区域，不一定是完整圆章
    aspect_ratio = max(width / height, height / width)
    if aspect_ratio >= 2.0:
        score += 0.2
    else:
        score += 0.1

    return min(score, 1.0)

def detect_cross_page_seal_fragments(
    image_path: str | Path,
    page_index: int
) -> list[CPSealFragment]: # 有可能检测出其他红色印章，本函数不参与骑缝章的鉴别。所以要把所有的都返回
    """
        检测单页合同图片的骑缝章片段
    """
    logger.info("开始检测骑缝章片段 page_index={}, image_path={}", page_index, image_path)

    image = load_image(image_path)
    red_mask = build_red_mask(image)
    clean_mask = clean_red_mask(red_mask)

    contours = find_red_contours(
        clean_mask,
        min_contour_area=CPSEAL_MIN_CONTOUR_AREA,
        max_contours=CPSEAL_MAX_CONTOURS_PER_PAGE,
    )
    boxes = [build_candidate_bbox(c) for c in contours]
    logger.info("红色候选轮廓数量 page_index={}, count={}", page_index, len(boxes))

    ret = []
    for box in boxes:
        red_area = _count_red_pixels(box, clean_mask)
        edge = _check_edge(box, image.shape[1], image.shape[0])
        score = _score_fragment(box, edge, red_area)
        ret.append(
            CPSealFragment(
                page_index=page_index,
                image_path=str(image_path),
                edge=edge,
                bbox=box,
                red_area=red_area,
                score=score,
                crop_path="",
            )
        )

        logger.info(
            "骑缝章候选 page_index={}, edge={}, bbox={}, red_area={}, score={:.2f}",
            page_index,
            edge,
            box,
            red_area,
            score,
        )

    logger.info("骑缝章片段检测完成 page_index={}, fragments={}", page_index, len(ret))
    return ret


def analyze_cross_page_seal_results(
    page_results: list[CPSealFragment]
) -> CPSealResult:
    """
    汇总所有页面的骑缝章候选片段，生成规则初审结果。

    行为说明：
    1. 输入是 detect_cross_page_seal_fragments 返回的 CPSealFragment 列表，
       这里不再重新识别图片，只基于候选片段做汇总判断。
    2. 先按 page_index 分组，并过滤出有效候选：
       - page_index 必须大于 0；
       - edge 不能是 "unknown"；
       - score 必须大于 0。
    3. 从有效候选中统计出现最多的边，作为 main_edge。
       骑缝章通常应连续出现在同一侧边缘，所以只把 main_edge 上的页面计入 detected_pages。
    4. 本函数不再按 1..page_count 计算缺失页。
       因为合同可能是正反面交替扫描，骑缝章只出现在正面；总页数不能直接作为完整性判断标准。
    5. 状态判定规则：
       - 没有任何输入片段：status="unknown"，risk_level="unknown"；
       - 有输入但没有有效候选：status="missing"，risk_level="high"；
       - 有有效候选：status="unclear"，risk_level="unknown"。
         规则层只说明“有疑似骑缝章片段”，最终完整性由多模态复审判断这些片段能否拼成完整章。
    6. 返回的 CPSealResult 是规则初审结果，不是最终大模型复审结论。
       后续 VLM 复审可以基于本结果、原图和候选裁剪图进一步修正 status/risk/reason。
    """
    fragments = list(page_results or [])
    if not fragments:
        logger.info("骑缝章汇总完成 fragments=0, status=unknown")
        return CPSealResult(
            status="unknown",
            risk_level="unknown",
            reason="未收到骑缝章候选片段，无法判断。",
        )

    page_count = max((fragment.page_index for fragment in fragments if fragment.page_index > 0), default=0)
    fragments_by_page: dict[int, list[CPSealFragment]] = defaultdict(list)
    image_path_by_page: dict[int, str] = {}
    for fragment in fragments:
        if fragment.page_index <= 0:
            continue
        fragments_by_page[fragment.page_index].append(fragment)
        image_path_by_page.setdefault(fragment.page_index, fragment.image_path)

    valid_fragments = [
        fragment
        for fragment in fragments
        if fragment.page_index > 0 and fragment.edge != "unknown" and fragment.score > 0
    ]

    if valid_fragments:
        edge_counter = Counter(fragment.edge for fragment in valid_fragments)
        main_edge = edge_counter.most_common(1)[0][0]
        detected_pages = sorted(
            {
                fragment.page_index
                for fragment in valid_fragments
                if fragment.edge == main_edge
            }
        )
    else:
        main_edge = "unknown"
        detected_pages = []

    missing_pages: list[int] = []

    page_result_items = [
        CPSealPageResult(
            page_index=page_index,
            image_path=image_path_by_page.get(page_index, ""),
            fragments=fragments_by_page.get(page_index, []),
        )
        for page_index in range(1, page_count + 1)
    ]

    if page_count == 0:
        status = "unknown"
        risk_level = "unknown"
        reason = "候选片段页码无效，无法判断骑缝章状态。"
    elif not detected_pages:
        status = "missing"
        risk_level = "high"
        reason = "未检测到靠近页面边缘的骑缝章候选片段。"
    else:
        status = "unclear"
        risk_level = "unknown"
        reason = (
            f"主要在{main_edge}侧检测到骑缝章候选片段，"
            "规则层不按总页数判断缺失；需由多模态复审判断片段整体能否拼成完整骑缝章。"
        )

    logger.info(
        "骑缝章汇总完成 page_count={}, status={}, main_edge={}, detected_pages={}, missing_pages={}, risk_level={}",
        page_count,
        status,
        main_edge,
        detected_pages,
        missing_pages,
        risk_level,
    )

    return CPSealResult(
        status=status,
        page_count=page_count,
        detected_pages=detected_pages,
        missing_pages=missing_pages,
        main_edge=main_edge,
        risk_level=risk_level,
        reason=reason,
        page_results=page_result_items,
    )

