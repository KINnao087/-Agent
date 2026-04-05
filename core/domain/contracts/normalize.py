from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation



_TEXT_REPLACEMENTS = {
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "：": ":",
    "，": ",",
    "；": ";",
    "、": ",",
    "　": " ",
}

def normalize_text(value: str) -> str:
    """普通文本归一化，用于名称、地址、支付方式等字段比较。"""
    if not value:
        return ""

    text = str(value).strip()
    for old, new in _TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)

    text = " ".join(text.split())
    return text.lower()


_EMPTY_MARKERS = {"", "-", "--", "/", "无", "暂无", "未填写"}

_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "贰": 2,
    "两": 2,
    "兩": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}

_SMALL_UNITS = {
    "十": 10,
    "拾": 10,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
}

_SECTION_UNITS = {
    "万": 10000,
    "萬": 10000,
    "亿": 100000000,
    "億": 100000000,
}

_ARABIC_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_CHINESE_AMOUNT_RE = re.compile(
    r"[零〇一二三四五六七八九壹贰叁肆伍陆柒捌玖两兩十拾百佰千仟万萬亿億圆元角分整正]+"
)

def _clean_amount_text(value: str) -> str:
    """清理金额文本中的常见噪声。"""
    if not value:
        return ""

    text = str(value).strip()
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("￥", "").replace("¥", "")
    text = text.replace("人民币", "").replace("RMB", "").replace("CNY", "")
    text = text.replace("，", ",").replace("．", ".")
    text = re.sub(r"\s+", "", text)
    return text

def _decimal_to_string(value: Decimal) -> str:
    """把 Decimal 转成稳定可比较的字符串，并去掉多余 0。"""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"

def _parse_arabic_amount(text: str) -> Decimal | None:
    """解析阿拉伯数字金额，并按尾部单位折算成元。"""
    match = _ARABIC_RE.search(text)
    if not match:
        return None

    raw_number = match.group().replace(",", "")
    try:
        value = Decimal(raw_number)
    except InvalidOperation:
        return None

    suffix = text[match.end() :]
    multiplier = Decimal("1")

    if suffix.startswith(("亿", "億")):
        multiplier = Decimal("100000000")
    elif suffix.startswith(("万", "萬")):
        multiplier = Decimal("10000")
    elif suffix.startswith("千"):
        multiplier = Decimal("1000")
    elif suffix.startswith("百"):
        multiplier = Decimal("100")

    return value * multiplier

def _parse_chinese_integer(text: str) -> int:
    """解析中文整数部分，例如“肆拾玖万” -> 490000。"""
    if not text:
        return 0

    if not any(char in _SMALL_UNITS or char in _SECTION_UNITS for char in text):
        digits = [_CHINESE_DIGITS[char] for char in text if char in _CHINESE_DIGITS]
        if digits:
            return int("".join(str(digit) for digit in digits))

    total = 0
    section = 0
    number = 0

    for char in text:
        if char in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[char]
        elif char in _SMALL_UNITS:
            unit = _SMALL_UNITS[char]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
        elif char in _SECTION_UNITS:
            unit = _SECTION_UNITS[char]
            section += number
            total += section * unit
            section = 0
            number = 0

    return total + section + number

def _parse_chinese_amount(text: str) -> Decimal | None:
    """解析中文大写金额，并折算成元。"""
    match = _CHINESE_AMOUNT_RE.search(text)
    if not match:
        return None

    candidate = match.group()
    candidate = candidate.replace("整", "").replace("正", "")

    integer_part = candidate
    fraction_part = ""
    for separator in ("元", "圆"):
        if separator in candidate:
            integer_part, fraction_part = candidate.split(separator, 1)
            break

    integer_value = Decimal(_parse_chinese_integer(integer_part)) if integer_part else Decimal("0")
    fraction_value = Decimal("0")

    jiao_match = re.search(
        r"([零〇一二三四五六七八九壹贰叁肆伍陆柒捌玖两兩])角",
        fraction_part,
    )
    if jiao_match:
        fraction_value += Decimal(_CHINESE_DIGITS[jiao_match.group(1)]) / Decimal("10")

    fen_match = re.search(
        r"([零〇一二三四五六七八九壹贰叁肆伍陆柒捌玖两兩])分",
        fraction_part,
    )
    if fen_match:
        fraction_value += Decimal(_CHINESE_DIGITS[fen_match.group(1)]) / Decimal("100")

    result = integer_value + fraction_value
    if result == 0 and candidate not in {"零", "零元"}:
        return None
    return result

def normalize_amount(value: str) -> str:
    """金额归一化，统一输出为以元为单位的标准数字字符串。"""
    text = _clean_amount_text(value)
    if text in _EMPTY_MARKERS:
        return ""

    arabic_value = _parse_arabic_amount(text)
    if arabic_value is not None:
        return _decimal_to_string(arabic_value)

    chinese_value = _parse_chinese_amount(text)
    if chinese_value is not None:
        return _decimal_to_string(chinese_value)

    return text.lower()


def normalize_phone(value: str) -> str:
    """电话归一化，仅保留数字用于比较。"""
    if not value:
        return ""
    return "".join(char for char in str(value) if char.isdigit())


def _has_chinese(s: str) -> bool:
    for ch in s:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False

_DATE_CH_RE = re.compile(
    r"(?P<year>\d{4})\s*年(?:\s*(?P<month>\d{1,2})\s*月(?:\s*(?P<day>\d{1,2})\s*[日号]?)?)?"
)
_DATE_EXTRACT_PATTERNS = (
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]"),
    re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月"),
    re.compile(r"\d{4}\s*年"),
    re.compile(r"\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}"),
    re.compile(r"\d{4}\s*[-/.]\s*\d{1,2}"),
    re.compile(r"\d{4}"),
)
_PERIOD_DATE_RE = re.compile(
    r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?"
    r"|\d{4}\s*年\s*\d{1,2}\s*月"
    r"|\d{4}\s*年"
    r"|\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}"
    r"|\d{4}\s*[-/.]\s*\d{1,2}"
    r"|\d{4}"
)
_DATE_AMBIGUOUS_SUFFIX_RE = re.compile(r"^(上旬|中旬|下旬|前|后|之前|之后|以前|以后)")
_PERIOD_CONNECTOR_RE = re.compile(r"(至|到|~|～|—|－|-|起至|起止|止于)")


def _is_valid_calendar_date(year: int, month: int, day: int) -> bool:
    """判断年月日是否是真实存在的日历日期。"""
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True

def _normalize_date_ch(text: str) -> str | None:
    """从字符串中提取并归一化单个中文日期。"""
    if not text:
        return None
    if not _has_chinese(text):
        return None

    matches = list(_DATE_CH_RE.finditer(str(text)))
    if len(matches) != 1:
        return None

    match = matches[0]
    year = int(match.group("year"))
    month_text = match.group("month")
    day_text = match.group("day")

    if month_text is None:
        return f"{year:04d}"

    month = int(month_text)
    if not 1 <= month <= 12:
        return None

    if day_text is None:
        return f"{year:04d}-{month:02d}"

    day = int(day_text)
    if not 1 <= day <= 31:
        return None
    if not _is_valid_calendar_date(year, month, day):
        return None

    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_date_text(text: str) -> str | None:
    """从原字符串中提取单个候选日期片段。"""
    if not text:
        return None

    raw_text = str(text).strip()
    if not raw_text:
        return None

    for pattern in _DATE_EXTRACT_PATTERNS:
        matches = list(pattern.finditer(raw_text))
        if len(matches) > 1:
            return None
        if len(matches) == 1:
            match = matches[0]
            suffix = raw_text[match.end() :].lstrip()
            if _DATE_AMBIGUOUS_SUFFIX_RE.match(suffix):
                return None
            return match.group(0)

    return None


def normalize_date(value: str) -> str:
    """日期归一化，建议统一成 YYYY-MM-DD。"""
    candidate = _extract_date_text(value)
    if candidate is None:
        return ""

    ret = _normalize_date_ch(candidate)
    if ret is not None:
        return ret

    cleaned = re.sub(r"\s+", "", candidate)
    for separator in (".", "/", "-"):
        parts = cleaned.split(separator)
        if len(parts) == 3:
            year, month, day = parts
            try:
                year_int = int(year)
                month_int = int(month)
                day_int = int(day)
            except ValueError:
                return ""
            if not _is_valid_calendar_date(year_int, month_int, day_int):
                return ""
            if len(month) == 1:
                month = "0" + month
            if len(day) == 1:
                day = "0" + day
            return "-".join([year, month, day])
        if len(parts) == 2:
            year, month = parts
            try:
                month_int = int(month)
            except ValueError:
                return ""
            if not 1 <= month_int <= 12:
                return ""
            if len(month) == 1:
                month = "0" + month
            return "-".join([year, month])

    if cleaned.isdigit() and len(cleaned) == 4:
        return cleaned
    return ""


def _extract_period_dates(text: str) -> list[re.Match[str]] | None:
    """从合同周期原文中提取两个候选日期片段。"""
    if not text:
        return None

    raw_text = str(text).strip()
    if not raw_text:
        return None

    matches = list(_PERIOD_DATE_RE.finditer(raw_text))
    if len(matches) != 2:
        return None

    for match in matches:
        suffix = raw_text[match.end() :].lstrip()
        if _DATE_AMBIGUOUS_SUFFIX_RE.match(suffix):
            return None

    between_text = raw_text[matches[0].end() : matches[1].start()]
    if not _PERIOD_CONNECTOR_RE.search(between_text):
        return None

    return matches


def normalize_period(value: str) -> str:
    """合同周期归一化，建议统一成 start~end 的可比较格式。"""
    matches = _extract_period_dates(value)
    if matches is None:
        return ""

    start = normalize_date(matches[0].group(0))
    end = normalize_date(matches[1].group(0))
    if not start or not end:
        return ""

    return f"{start}~{end}"


def normalize_value(value: str, kind: str) -> str:
    """按字段类型分派到对应的归一化函数。"""
    if kind == "text":
        return normalize_text(value)
    if kind == "phone":
        return normalize_phone(value)
    if kind == "amount":
        return normalize_amount(value)
    if kind == "date":
        return normalize_date(value)
    if kind == "period":
        return normalize_period(value)
    raise ValueError(f"unsupported normalize kind: {kind}")
