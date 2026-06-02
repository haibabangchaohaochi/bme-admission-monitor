from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scripts.merge_schools import build_status
from scripts.notify import notify
from scripts.parse_notice import classify_notice
from scripts.utils import DATA_DIR, DOCS_DIR, clean_text, extract_first_date_text, now_cn_iso, read_json, write_json


TIMEOUT = 15
KEYWORDS = ["夏令营", "暑期学校", "预推免", "推免", "夏令营通知", "招生", "开放日", "优秀大学生"]
CHANGE_FIELDS = [
    "summer_camp_status",
    "pre_recommend_status",
    "latest_notice_title",
    "latest_notice_url",
    "registration_deadline",
    "event_time",
    "source_type",
    "source_reliability",
]


def source_type_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if any(token in path for token in ["yz", "yjs", "graduate", "admission", "zhaosheng"]):
        return "研究生招生网"
    if any(token in host for token in ["yz", "yjs", "graduate", "admission"]):
        return "研究生院"
    return "学院官网"


def source_reliability(source_type: str) -> str:
    return "high" if source_type in {"研究生院", "研究生招生网", "学院官网"} else "low"


def fetch_page(url: str) -> tuple[str, str, str, list[tuple[str, str]]]:
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")
    title = clean_text(soup.title.get_text(" ")) if soup.title else ""
    text = clean_text(soup.get_text(" "))
    links: list[tuple[str, str]] = []
    for anchor in soup.select("a[href]"):
        label = clean_text(anchor.get_text(" "))
        href = urljoin(response.url, anchor.get("href", ""))
        if any(keyword in f"{label} {href}" for keyword in KEYWORDS) or re.search(r"20(24|25|26)", f"{label} {href}"):
            links.append((label, href))
    return response.url, title, text, links[:20]


def analyze_links(page_url: str, title: str, text: str, links: list[tuple[str, str]]) -> dict[str, Any]:
    source_type = source_type_from_url(page_url)
    quality = source_reliability(source_type)
    parsed = classify_notice(title=title, body=text, source_type=source_type, source_reliability=quality, source_url=page_url)
    result: dict[str, Any] = {
        "summer_camp_status": parsed.get("summer_camp_status"),
        "pre_recommend_status": parsed.get("pre_recommend_status"),
        "latest_notice_title": title,
        "latest_notice_url": page_url,
        "latest_notice_date": parsed.get("notice_date") or now_cn_iso().split("T", 1)[0],
        "registration_deadline": parsed.get("registration_deadline") or "",
        "event_time": parsed.get("event_time") or "",
        "source_type": source_type,
        "source_reliability": quality,
        "matched_keywords": parsed.get("matched_keywords", []),
        "candidate_links": [page_url],
    }

    for label, link in links[:8]:
        result["candidate_links"].append(link)
        try:
            link_url, link_title, link_text, _ = fetch_page(link)
        except Exception:  # noqa: BLE001
            continue
        link_type = source_type_from_url(link_url)
        link_quality = source_reliability(link_type)
        link_parsed = classify_notice(title=link_title or label, body=link_text, source_type=link_type, source_reliability=link_quality, source_url=link_url)
        if not result.get("latest_notice_title") and link_title:
            result["latest_notice_title"] = link_title
            result["latest_notice_url"] = link_url
        if link_parsed.get("summer_camp_status") in {"已发布", "疑似发布"} and not result.get("summer_camp_status"):
            result["summer_camp_status"] = link_parsed["summer_camp_status"]
            result["latest_notice_title"] = link_title or label
            result["latest_notice_url"] = link_url
            result["latest_notice_date"] = link_parsed.get("notice_date") or result["latest_notice_date"]
            result["registration_deadline"] = link_parsed.get("registration_deadline") or result["registration_deadline"]
            result["event_time"] = link_parsed.get("event_time") or result["event_time"]
            result["source_type"] = link_type
            result["source_reliability"] = link_quality
            result["matched_keywords"] = link_parsed.get("matched_keywords", [])
        if link_parsed.get("pre_recommend_status") in {"已发布", "疑似发布"} and not result.get("pre_recommend_status"):
            result["pre_recommend_status"] = link_parsed["pre_recommend_status"]
            result["latest_notice_title"] = link_title or label
            result["latest_notice_url"] = link_url
            result["latest_notice_date"] = link_parsed.get("notice_date") or result["latest_notice_date"]
            result["registration_deadline"] = link_parsed.get("registration_deadline") or result["registration_deadline"]
            result["event_time"] = link_parsed.get("event_time") or result["event_time"]
            result["source_type"] = link_type
            result["source_reliability"] = link_quality
            result["matched_keywords"] = link_parsed.get("matched_keywords", [])

    return result


def compare_and_update(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in CHANGE_FIELDS:
        if old.get(key) != new.get(key):
            changes.append({"field_name": key, "old_value": old.get(key, ""), "new_value": new.get(key, "")})
    return changes


def deadline_to_status(current_status: str | None, deadline: str | None) -> str | None:
    if current_status not in {"已发布", "疑似发布", "报名中"}:
        return current_status
    normalized = extract_first_date_text(deadline)
    if not normalized:
        return current_status
    try:
        deadline_dt = datetime.fromisoformat(normalized).replace(tzinfo=timezone(timedelta(hours=8)))
    except ValueError:
        return current_status
    hours_left = (deadline_dt - datetime.now(timezone(timedelta(hours=8)))).total_seconds() / 3600
    if 0 <= hours_left <= 72:
        return "报名中"
    if hours_left < 0:
        return "已截止"
    return current_status


def write_history_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    history_path = DATA_DIR / "history.csv"
    fieldnames = ["timestamp", "school_id", "school_name", "event_type", "field_name", "old_value", "new_value", "source_type", "source_url", "source_title", "notes"]
    exists = history_path.exists() and history_path.stat().st_size > 0
    with history_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    previous = read_json(DATA_DIR / "status.json", default={"schools": []}) or {"schools": []}
    previous_map = {item["id"]: item for item in previous.get("schools", [])}
    current = build_status()
    now = now_cn_iso()

    history_rows: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []

    for school in current.get("schools", []):
        school_id = school["id"]
        old_school = previous_map.get(school_id, {})
        best: dict[str, Any] = {}
        candidate_links: list[str] = list(school.get("candidate_links", []))
        manual_override = bool(school.get("manual_override"))

        for url in school.get("official_sites", []):
            try:
                page_url, title, text, links = fetch_page(url)
            except Exception:  # noqa: BLE001
                candidate_links.append(url)
                continue
            best = analyze_links(page_url, title, text, links)
            candidate_links.extend(best.get("candidate_links", []))
            if best.get("summer_camp_status") == "已发布" or best.get("pre_recommend_status") == "已发布":
                break

        if not best:
            best = {
                "candidate_links": candidate_links,
                "source_type": "搜索结果",
                "source_reliability": "low",
                "matched_keywords": [],
            }

        for key, value in best.items():
            if key in {"summer_camp_status", "pre_recommend_status", "latest_notice_title", "latest_notice_url", "latest_notice_date", "registration_deadline", "event_time", "source_type", "source_reliability", "matched_keywords"}:
                if manual_override and school.get(key):
                    continue
                if value not in (None, ""):
                    school[key] = value

        school["candidate_links"] = list(dict.fromkeys(candidate_links + list(school.get("candidate_links", []))))
        school["last_checked_at"] = now

        if not manual_override:
            school["summer_camp_status"] = deadline_to_status(school.get("summer_camp_status"), school.get("registration_deadline")) or school.get("summer_camp_status")
            school["pre_recommend_status"] = deadline_to_status(school.get("pre_recommend_status"), school.get("registration_deadline")) or school.get("pre_recommend_status")

        changes = compare_and_update(old_school, school)
        if changes:
            school["last_changed_at"] = now
            school["change_summary"] = "；".join(f"{item['field_name']} 变更" for item in changes)
            for change in changes:
                history_rows.append(
                    {
                        "timestamp": now,
                        "school_id": school_id,
                        "school_name": school.get("name", ""),
                        "event_type": "update",
                        "field_name": change["field_name"],
                        "old_value": change["old_value"],
                        "new_value": change["new_value"],
                        "source_type": school.get("source_type", ""),
                        "source_url": school.get("latest_notice_url", ""),
                        "source_title": school.get("latest_notice_title", ""),
                        "notes": school.get("notes", ""),
                    }
                )

        history_rows.append(
            {
                "timestamp": now,
                "school_id": school_id,
                "school_name": school.get("name", ""),
                "event_type": "check",
                "field_name": "last_checked_at",
                "old_value": old_school.get("last_checked_at", ""),
                "new_value": school.get("last_checked_at", ""),
                "source_type": school.get("source_type", ""),
                "source_url": school.get("latest_notice_url", ""),
                "source_title": school.get("latest_notice_title", ""),
                "notes": school.get("notes", ""),
            }
        )

        if old_school.get("latest_notice_title", "") != school.get("latest_notice_title", "") and school.get("latest_notice_title"):
            notifications.append(
                {
                    "school_name": school.get("name", ""),
                    "notice_kind": "夏令营 / 预推免",
                    "status": school.get("summer_camp_status") if school.get("summer_camp_status") != "未发布" else school.get("pre_recommend_status"),
                    "latest_notice_title": school.get("latest_notice_title", ""),
                    "registration_deadline": school.get("registration_deadline", ""),
                    "event_time": school.get("event_time", ""),
                    "source_type": school.get("source_type", ""),
                    "latest_notice_url": school.get("latest_notice_url", ""),
                }
            )

        if school.get("summer_camp_status") in {"疑似发布", "已发布", "报名中"} and old_school.get("summer_camp_status", "未发布") == "未发布":
            notifications.append(
                {
                    "school_name": school.get("name", ""),
                    "notice_kind": "夏令营",
                    "status": school.get("summer_camp_status", ""),
                    "latest_notice_title": school.get("latest_notice_title", ""),
                    "registration_deadline": school.get("registration_deadline", ""),
                    "event_time": school.get("event_time", ""),
                    "source_type": school.get("source_type", ""),
                    "latest_notice_url": school.get("latest_notice_url", ""),
                }
            )

        if school.get("pre_recommend_status") in {"疑似发布", "已发布", "报名中"} and old_school.get("pre_recommend_status", "未发布") == "未发布":
            notifications.append(
                {
                    "school_name": school.get("name", ""),
                    "notice_kind": "预推免",
                    "status": school.get("pre_recommend_status", ""),
                    "latest_notice_title": school.get("latest_notice_title", ""),
                    "registration_deadline": school.get("registration_deadline", ""),
                    "event_time": school.get("event_time", ""),
                    "source_type": school.get("source_type", ""),
                    "latest_notice_url": school.get("latest_notice_url", ""),
                }
            )

        if school.get("registration_deadline"):
            try:
                deadline_dt = datetime.fromisoformat(extract_first_date_text(school["registration_deadline"]) or school["registration_deadline"]).replace(tzinfo=timezone(timedelta(hours=8)))
            except ValueError:
                deadline_dt = None
            if deadline_dt:
                hours_left = (deadline_dt - datetime.now(timezone(timedelta(hours=8)))).total_seconds() / 3600
                if 0 <= hours_left <= 72:
                    notifications.append(
                        {
                            "school_name": school.get("name", ""),
                            "notice_kind": "夏令营 / 预推免",
                            "status": school.get("summer_camp_status", school.get("pre_recommend_status", "")),
                            "latest_notice_title": school.get("latest_notice_title", ""),
                            "registration_deadline": school.get("registration_deadline", ""),
                            "event_time": school.get("event_time", ""),
                            "source_type": school.get("source_type", ""),
                            "latest_notice_url": school.get("latest_notice_url", ""),
                        }
                    )

    write_json(DATA_DIR / "status.json", current)
    write_json(DOCS_DIR / "status.json", current)
    write_history_rows(history_rows)

    for notification in notifications:
        notify(notification)

    print(f"[check_updates] checked {len(current.get('schools', []))} schools")


if __name__ == "__main__":
    main()