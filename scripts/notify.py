from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

import requests


def format_notification(record: dict[str, Any]) -> str:
    lines = [
        "【保研监控提醒】",
        f"学校：{record.get('school_name', '')}",
        f"类型：{record.get('notice_kind', '夏令营 / 预推免')}",
        f"状态：{record.get('status', '')}",
        f"公告标题：{record.get('latest_notice_title', '')}",
        f"报名截止：{record.get('registration_deadline', '')}",
        f"活动时间：{record.get('event_time', '')}",
        f"来源类型：{record.get('source_type', '')}",
        f"链接：{record.get('latest_notice_url', '')}",
        "建议：请尽快人工核验报名条件、材料要求、招生专业和导师方向。",
    ]
    return "\n".join(lines)


def _post_json(url: str, payload: dict[str, Any]) -> None:
    requests.post(url, json=payload, timeout=15)


def send_pushplus(message: str) -> bool:
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        return False
    _post_json("https://www.pushplus.plus/send", {"token": token, "title": "保研监控提醒", "content": message})
    return True


def send_bark(message: str) -> bool:
    key = os.getenv("BARK_KEY")
    if not key:
        return False
    base_url = key.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://api.day.app/{base_url}"
    _post_json(base_url, {"title": "保研监控提醒", "body": message})
    return True


def send_wecom(message: str) -> bool:
    webhook = os.getenv("WECOM_WEBHOOK")
    if not webhook:
        return False
    _post_json(webhook, {"msgtype": "text", "text": {"content": message}})
    return True


def send_smtp(message: str) -> bool:
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_email = os.getenv("NOTIFY_EMAIL_TO")
    if not all([host, user, password, to_email]):
        return False
    email_message = EmailMessage()
    email_message["Subject"] = "保研监控提醒"
    email_message["From"] = user
    email_message["To"] = to_email
    email_message.set_content(message)
    with smtplib.SMTP(host, 587, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(email_message)
    return True


def notify(record: dict[str, Any]) -> None:
    message = format_notification(record)
    delivered = False
    for sender in (send_pushplus, send_bark, send_wecom, send_smtp):
        try:
            delivered = sender(message) or delivered
        except Exception as exc:  # noqa: BLE001
            print(f"[notify] {sender.__name__} failed: {exc}")
    if not delivered:
        print(message)
