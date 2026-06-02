from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from scripts.utils import clean_text, parse_date_like


SUMMER_KEYWORDS = ["优秀大学生夏令营", "暑期学校", "夏令营", "校园开放日", "学术夏令营", "开放日"]
PRE_KEYWORDS = ["预推免", "推免生接收", "推荐免试研究生", "接收推荐免试研究生", "免试攻读研究生", "推免"]
OFFICIAL_HINTS = ["研究生院", "研究生招生网", "招生网", "学院官网", "官网"]


@dataclass
class ParsedNotice:
    title: str = ""
    body: str = ""
    notice_date: str | None = None
    year: int | None = None
    has_2026: bool = False
    has_historical_year: bool = False
    matched_keywords: list[str] | None = None
    summer_camp_status: str | None = None
    pre_recommend_status: str | None = None
    source_reliability: str | None = None
    source_type: str | None = None
    candidate_link: str | None = None
    risk_flag: str | None = None
    notes: str | None = None
    registration_deadline: str | None = None
    event_time: str | None = None


def _extract_year(text: str) -> int | None:
    match = re.search(r"(20\d{2})", text)
    if not match:
        return None
    return int(match.group(1))


def _has_historical_year(text: str) -> bool:
    return bool(re.search(r"20(24|25)(?!级)", text))


def _match_keywords(text: str) -> list[str]:
    keywords = []
    for keyword in SUMMER_KEYWORDS + PRE_KEYWORDS:
        if keyword in text and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def _extract_by_labels(text: str, labels: list[str]) -> str | None:
    for label in labels:
        match = re.search(rf"{label}[:：]?\s*([^。；;\n]{{0,40}})", text)
        if match:
            candidate = clean_text(match.group(1))
            if candidate:
                return candidate
    return None


def _extract_deadline(text: str) -> str | None:
    candidate = _extract_by_labels(text, ["报名截止", "截止报名", "网申截止", "申请截止"])
    return parse_date_like(candidate) if candidate else None


def _extract_event_time(text: str) -> str | None:
    candidate = _extract_by_labels(text, ["活动时间", "夏令营时间", "举办时间", "时间"])
    if candidate:
        return candidate
    date_match = re.search(r"20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}日?(?:至|到|—|-|~|～)20?\d{0,2}[年/-]?\d{1,2}[月/-]?\d{0,2}日?", text)
    if date_match:
        return clean_text(date_match.group(0))
    return None


def classify_notice(
    title: str,
    body: str,
    notice_date: str | None = None,
    source_type: str = "搜索结果",
    source_reliability: str = "low",
    source_url: str | None = None,
) -> dict[str, Any]:
    combined = clean_text(f"{title} {body}")
    year = _extract_year(combined)
    has_2026 = "2026" in combined
    has_historical_year = _has_historical_year(combined)
    matched_keywords = _match_keywords(combined)
    official_source = source_type in {"研究生院", "研究生招生网", "招生网", "学院官网"}
    official_quality = source_reliability == "high" or official_source
    summer_hit = any(keyword in combined for keyword in SUMMER_KEYWORDS)
    pre_hit = any(keyword in combined for keyword in PRE_KEYWORDS)

    summer_camp_status = None
    pre_recommend_status = None
    risk_flag = None
    notes = None

    if has_2026 and summer_hit:
        summer_camp_status = "已发布" if official_quality else "疑似发布"
    elif not has_2026 and summer_hit and source_reliability in {"medium", "low"}:
        summer_camp_status = "需人工核验"

    if has_2026 and pre_hit:
        pre_recommend_status = "已发布" if official_quality else "疑似发布"
    elif not has_2026 and pre_hit and source_reliability in {"medium", "low"}:
        pre_recommend_status = "需人工核验"

    if has_historical_year and not has_2026:
        risk_flag = "历史年份公告，避免误判为 2026"

    if re.search(r"20(24|25)级", combined):
        notes = "标题或正文出现年级信息，需人工确认是否为招生年份。"
        if not has_2026:
            risk_flag = "年级信息干扰，需人工核验"

    parsed_date = parse_date_like(notice_date) if notice_date else None
    registration_deadline = _extract_deadline(combined)
    event_time = _extract_event_time(combined)

    return asdict(
        ParsedNotice(
            title=title,
            body=body,
            notice_date=parsed_date,
            year=year,
            has_2026=has_2026,
            has_historical_year=has_historical_year,
            matched_keywords=matched_keywords,
            summer_camp_status=summer_camp_status,
            pre_recommend_status=pre_recommend_status,
            source_reliability=source_reliability,
            source_type=source_type,
            candidate_link=source_url,
            risk_flag=risk_flag,
            notes=notes,
            registration_deadline=registration_deadline,
            event_time=event_time,
        )
    )
