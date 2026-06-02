from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return default if data is None else data


def write_yaml(path: Path, data: Any) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def append_csv_row(path: Path, row: dict[str, Any]) -> None:
    ensure_parent(path)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def now_cn_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()


def today_cn() -> str:
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def slug_id(text: str) -> str:
    ascii_text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if ascii_text:
        return ascii_text
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"school-{digest}"


def safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_date_like(value: str | None) -> str | None:
    if not value:
        return None
    text = clean_text(value)
    patterns = [
        (r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", False),
        (r"(20\d{2})年?(\d{1,2})月(\d{1,2})日?", False),
        (r"(20\d{2})-(\d{1,2})-(\d{1,2})", True),
    ]
    for pattern, already_iso in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month, day = map(int, match.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            continue
    return None


def extract_first_date_text(value: str | None) -> str | None:
    if not value:
        return None
    text = clean_text(value)
    match = re.search(r"(20\d{2})[年/-](\d{1,2})(?:[月/-](\d{1,2}))?日?", text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3) or 1)
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def merge_unique(*values: list[Any]) -> list[Any]:
    seen = []
    for value_list in values:
        for item in value_list:
            if item not in seen:
                seen.append(item)
    return seen


def flatten_text(items: list[Any]) -> str:
    return " ".join(str(item) for item in items if item)
