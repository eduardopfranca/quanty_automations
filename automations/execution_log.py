"""
execution_log.py
Manages execution_log.json, which records:
  - last successful run of each job
  - last attempt (success or failure)
  - rolling history of the last N results

JSON format:
{
    "factor_db": {
        "last_success": "2025-06-10T09:12:33",
        "last_attempt": "2025-06-10T09:12:33",
        "last_status": "SUCCESS",
        "last_error": null,
        "last_duration_seconds": 142.5,
        "history": [
            {
                "timestamp": "2025-06-10T09:12:33",
                "status": "SUCCESS",
                "duration_seconds": 142.5,
                "error": null
            },
            ...
        ]
    },
    ...
}
"""

import json
from datetime import datetime
from pathlib import Path

# Maximum history entries per job (prevents unbounded growth)
MAX_HISTORY_ENTRIES = 30


def _load_raw(log_path: Path) -> dict:
    """Loads JSON from disk. Returns empty dict if file does not exist."""
    if not log_path.exists():
        return {}
    try:
        text = log_path.read_text(encoding="utf-8")
        return json.loads(text) if text.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict, log_path: Path) -> None:
    """Saves dict to disk as indented JSON."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def get_last_success(log_path: Path, job_name: str) -> datetime | None:
    """
    Returns the datetime of the last successful run for the given job,
    or None if it has never succeeded.
    """
    data = _load_raw(log_path)
    job_data = data.get(job_name)
    if not job_data:
        return None
    ts = job_data.get("last_success")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def get_last_attempt(log_path: Path, job_name: str) -> dict | None:
    """
    Returns a dict with info about the last attempt:
    {
        "timestamp": datetime,
        "status": "SUCCESS" | "FAILED" | "SKIPPED",
        "error": str | None,
        "duration_seconds": float
    }
    Returns None if no attempt has been recorded.
    """
    data = _load_raw(log_path)
    job_data = data.get(job_name)
    if not job_data or not job_data.get("last_attempt"):
        return None
    return {
        "timestamp": job_data.get("last_attempt"),
        "status":    job_data.get("last_status"),
        "error":     job_data.get("last_error"),
        "duration_seconds": job_data.get("last_duration_seconds"),
    }


def get_all_jobs_summary(log_path: Path) -> dict:
    """
    Returns a summary of all recorded jobs:
    {
        "job_name": {
            "last_success": "...",
            "last_status": "...",
            "last_attempt": "...",
            "last_duration_seconds": ...,
            "last_error": "...",
        },
        ...
    }
    """
    data = _load_raw(log_path)
    summary = {}
    for job_name, job_data in data.items():
        summary[job_name] = {
            "last_success":          job_data.get("last_success"),
            "last_status":           job_data.get("last_status"),
            "last_attempt":          job_data.get("last_attempt"),
            "last_duration_seconds": job_data.get("last_duration_seconds"),
            "last_error":            job_data.get("last_error"),
        }
    return summary


def record_result(
    log_path: Path,
    job_name: str,
    status: str,
    duration_seconds: float = 0.0,
    error: str | None = None,
) -> None:
    """
    Records the result of a job execution or attempt.

    Args:
        log_path:         path to execution_log.json
        job_name:         job identifier (e.g. "factor_db")
        status:           "SUCCESS", "FAILED", or "SKIPPED"
        duration_seconds: execution time in seconds
        error:            error message if applicable
    """
    data = _load_raw(log_path)

    now_iso = datetime.now().isoformat(timespec="seconds")

    if job_name not in data:
        data[job_name] = {
            "last_success":          None,
            "last_attempt":          None,
            "last_status":           None,
            "last_error":            None,
            "last_duration_seconds": None,
            "history":               [],
        }

    job_data = data[job_name]

    # Update last attempt fields
    job_data["last_attempt"]          = now_iso
    job_data["last_status"]           = status
    job_data["last_error"]            = error
    job_data["last_duration_seconds"] = round(duration_seconds, 2)

    # On success, update last_success
    if status == "SUCCESS":
        job_data["last_success"] = now_iso

    # Append to history
    entry = {
        "timestamp":        now_iso,
        "status":           status,
        "duration_seconds": round(duration_seconds, 2),
        "error":            error,
    }
    job_data["history"].append(entry)

    # Trim history to max size
    if len(job_data["history"]) > MAX_HISTORY_ENTRIES:
        job_data["history"] = job_data["history"][-MAX_HISTORY_ENTRIES:]

    _save_raw(data, log_path)