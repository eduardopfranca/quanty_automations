"""
notifier.py
Sends a consolidated email summary after each automate run.
"""
from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from .config import Settings


def _subject(results: list[dict]) -> str:
    statuses = {r["status"] for r in results}
    if "FAILED" in statuses:
        return "[ERROR]"
    if "SUCCESS" in statuses:
        return "[OK]"
    return "[INFO]"


def _body(results: list[dict], start: datetime, end: datetime) -> str:
    lines = []

    total_seconds = int((end - start).total_seconds())
    mins, secs = divmod(total_seconds, 60)
    duration_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    lines.append(f"[automate] run finished — {start.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Results table
    lines.append("RESULTS")
    icons = {"SUCCESS": "v", "FAILED": "X", "SKIPPED": "-", "DRY_RUN": "o"}
    for r in results:
        icon = icons.get(r["status"], "?")
        dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "-"
        lines.append(
            f"  [{icon}] {r['status']:<10}  {r['job']:<20}  {dur:>8}   {r['message']}"
        )
    lines.append("")

    # Report files (optional, per job)
    reports = []
    for r in results:
        rf = r.get("report_file")
        if rf and Path(rf).exists():
            try:
                content = Path(rf).read_text(encoding="utf-8").strip()
                if content:
                    reports.append((r["job"], content))
            except OSError:
                pass

    if reports:
        lines.append("REPORTS")
        for job_name, content in reports:
            separator = "-" * max(4, 40 - len(job_name))
            lines.append(f"  -- {job_name} {separator}")
            for line in content.splitlines():
                lines.append(f"  {line}")
            lines.append("")

    # Summary
    n_success = sum(1 for r in results if r["status"] == "SUCCESS")
    n_failed  = sum(1 for r in results if r["status"] == "FAILED")
    n_skipped = sum(1 for r in results if r["status"] in ("SKIPPED", "DRY_RUN"))

    lines.append("SUMMARY")
    lines.append(f"  Started : {start.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Finished: {end.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Duration: {duration_str}")
    lines.append(f"  Jobs    : {n_success} success, {n_failed} failed, {n_skipped} skipped")

    return "\n".join(lines)


def send_summary(
    settings: Settings,
    results: list[dict],
    start: datetime,
    end: datetime,
) -> None:
    """
    Sends consolidated email. Skips silently if:
    - email is not configured (no sender or recipients)
    - email_on_success is False and there are no failures
    """
    if not settings.sender_email or not settings.recipients:
        return

    statuses = {r["status"] for r in results}
    if not settings.email_on_success and "FAILED" not in statuses:
        return

    subject = f"{_subject(results)} automate — {end.strftime('%Y-%m-%d %H:%M')}"
    body    = _body(results, start, end)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = settings.sender_email
    msg["To"]      = ", ".join(settings.recipients)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(settings.sender_email, settings.recipients, msg.as_string())