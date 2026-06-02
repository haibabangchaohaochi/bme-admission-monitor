from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.utils import (
    DATA_DIR,
    DOCS_DIR,
    append_csv_row,
    clean_text,
    merge_unique,
    now_cn_iso,
    read_csv_rows,
    read_json,
    read_yaml,
    safe_list,
    slug_id,
    write_json,
)


DEFAULT_SUMMER_STATUS = "未发布"
DEFAULT_PRE_STATUS = "未发布"
DEFAULT_WINDOW = "暂无可靠历史参考，需人工跟进"
DEFAULT_LEVEL_PRIORITY = {"985": "high", "211": "medium", "双非": "low", "科研院所": "high"}


def _default_city(level: str) -> str:
    return ""


def _default_expected_window(school: dict[str, Any]) -> str:
    level = school.get("level", "")
    if level in {"985", "科研院所"}:
        return "预计 2026 年 5 月下旬至 6 月上旬发布；预计 2026 年 6 月中下旬报名截止；预计 2026 年 7 月上旬活动"
    if level == "211":
        return "预计 2026 年 5 月至 6 月发布；预计 2026 年 6 月至 7 月报名截止；预计 2026 年 7 月活动"
    return DEFAULT_WINDOW


def _history_by_school(history_rows: list[dict[str, str]], school_id: str) -> list[dict[str, str]]:
    return [row for row in history_rows if row.get("school_id") == school_id]


def _derive_expected_window(history_rows: list[dict[str, str]], school: dict[str, Any]) -> tuple[str, str | None]:
    school_history = _history_by_school(history_rows, school["id"])
    years_text = " ".join(
        [row.get("old_value", "") + " " + row.get("new_value", "") + " " + row.get("source_title", "") for row in school_history]
    )
    if "2025" in years_text:
        return _default_expected_window(school), None
    if "2024" in years_text and "2025" not in years_text:
        return _default_expected_window(school), "2024 举办但 2025 未见，2026 是否继续举办需重点跟进"
    return _default_expected_window(school), None


def _normalize_school(raw: dict[str, Any], aliases_map: dict[str, Any], history_rows: list[dict[str, str]]) -> dict[str, Any]:
    school = deepcopy(raw)
    school_id = school.get("id") or slug_id(school.get("name", ""))
    school["id"] = school_id
    school.setdefault("aliases", [])
    school.setdefault("official_sites", [])
    school.setdefault("search_domains", [])
    school.setdefault("target_colleges", [])
    school.setdefault("preferred_directions", [])
    school.setdefault("priority", DEFAULT_LEVEL_PRIORITY.get(school.get("level", ""), "medium"))
    school.setdefault("summer_camp_status", DEFAULT_SUMMER_STATUS)
    school.setdefault("pre_recommend_status", DEFAULT_PRE_STATUS)
    school.setdefault("latest_notice_title", "")
    school.setdefault("latest_notice_url", "")
    school.setdefault("latest_notice_date", "")
    school.setdefault("registration_deadline", "")
    school.setdefault("event_time", "")
    school.setdefault("source_type", "搜索结果")
    school.setdefault("source_reliability", "low")
    school.setdefault("matched_keywords", [])
    school.setdefault("candidate_links", [])
    school.setdefault("last_checked_at", "")
    school.setdefault("last_changed_at", "")
    school.setdefault("change_summary", "初始生成")
    school.setdefault("manual_override", False)
    school.setdefault("notes", "")
    school.setdefault("risk_note", "")

    if school_id in aliases_map:
        alias_entry = aliases_map[school_id]
        school["aliases"] = merge_unique(safe_list(alias_entry.get("aliases")), school["aliases"])

    expected_window, risk_note = _derive_expected_window(history_rows, school)
    school["expected_release_window"] = school.get("expected_release_window") or expected_window
    if risk_note and not school.get("risk_note"):
        school["risk_note"] = risk_note

    return school


def build_status() -> dict[str, Any]:
    schools_yaml = read_yaml(DATA_DIR / "schools.yaml", default={"schools": []})
    extra_yaml = read_yaml(DATA_DIR / "extra_schools.yaml", default={"schools": []})
    aliases_yaml = read_yaml(DATA_DIR / "aliases.yaml", default={"aliases": {}})
    manual_overrides = read_yaml(DATA_DIR / "manual_overrides.yaml", default={"schools": {}})
    history_rows = read_csv_rows(DATA_DIR / "history.csv")

    aliases_map = aliases_yaml.get("aliases", {}) or {}
    combined = []
    for raw_school in safe_list(schools_yaml.get("schools", [])) + safe_list(extra_yaml.get("schools", [])):
        normalized = _normalize_school(raw_school, aliases_map, history_rows)
        override = manual_overrides.get("schools", {}).get(normalized["id"], {})
        if override:
            normalized.update(override)
            normalized["manual_override"] = True
        combined.append(normalized)

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    combined.sort(key=lambda item: (priority_rank.get(item.get("priority", "medium"), 1), item.get("name", "")))
    payload = {
        "generated_at": now_cn_iso(),
        "school_count": len(combined),
        "schools": combined,
        "recent_history": history_rows[-200:],
    }
    return payload


def main() -> None:
    status = build_status()
    write_json(DATA_DIR / "status.json", status)
    write_json(DOCS_DIR / "status.json", status)
    print(f"[merge_schools] merged {status['school_count']} schools")


if __name__ == "__main__":
    main()
