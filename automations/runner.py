"""
runner.py
Decides eligibility, executes jobs via subprocess, records results.
"""
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import execution_log as elog
from .config import Config, JobConfig

LOG_DIR = Path("logs")
EXECUTION_LOG_PATH = LOG_DIR / "execution_log.json"

_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _is_eligible(job: JobConfig, log_path: Path, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "forced"

    sc = job.schedule

    if sc.days_of_week:
        today = datetime.now().weekday()
        allowed = {_DAY_MAP[d] for d in sc.days_of_week}
        if today not in allowed:
            names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            return False, f"today is {names[today]}, job runs on {sc.days_of_week}"

    if sc.day_of_month is not None:
        if datetime.now().day != sc.day_of_month:
            return False, f"job runs on day {sc.day_of_month} of the month"

    if sc.min_interval_hours is not None:
        last = elog.get_last_success(log_path, job.name)
        if last is not None:
            elapsed = (datetime.now() - last).total_seconds() / 3600
            if elapsed < sc.min_interval_hours:
                return False, (
                    f"last run {elapsed:.1f}h ago "
                    f"(min interval: {sc.min_interval_hours}h)"
                )

    return True, "eligible"


def _check_success(proc: subprocess.CompletedProcess, job: JobConfig) -> bool:
    if proc.returncode != 0:
        return False
    if job.result.failure_marker and job.result.failure_marker in (proc.stdout or ""):
        return False
    if job.result.success_marker:
        return job.result.success_marker in (proc.stdout or "")
    return True


def _short_error(proc: subprocess.CompletedProcess) -> str:
    stderr = proc.stderr or ""
    lines = [l for l in stderr.splitlines() if l.strip() and not l.startswith("  ")]
    return (lines[-1] if lines else f"exit code {proc.returncode}")[:200]


def run_job(
    job: JobConfig,
    log_path: Path = EXECUTION_LOG_PATH,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    eligible, reason = _is_eligible(job, log_path, force)

    if not eligible:
        if not dry_run:
            elog.record_result(log_path, job.name, "SKIPPED", error=reason)
        return {
            "job": job.name,
            "status": "SKIPPED",
            "duration_seconds": 0.0,
            "message": reason,
            "report_file": None,
        }

    if dry_run:
        return {
            "job": job.name,
            "status": "DRY_RUN",
            "duration_seconds": 0.0,
            "message": "eligible — not executed",
            "report_file": None,
        }

    cmd = [str(job.python), str(job.script)] + list(job.args)
    cwd = str(job.cwd) if job.cwd else None
    start = time.monotonic()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=job.timeout_seconds,
            cwd=cwd,
        )
        duration = time.monotonic() - start

        if _check_success(proc, job):
            elog.record_result(log_path, job.name, "SUCCESS", duration)
            stdout_lines = (proc.stdout or "").strip().splitlines()
            message = stdout_lines[-1][:200] if stdout_lines else "ok"
            return {
                "job": job.name,
                "status": "SUCCESS",
                "duration_seconds": duration,
                "message": message,
                "report_file": job.result.report_file,
            }
        else:
            error = _short_error(proc)
            elog.record_result(log_path, job.name, "FAILED", duration, error=error)
            return {
                "job": job.name,
                "status": "FAILED",
                "duration_seconds": duration,
                "message": error,
                "report_file": job.result.report_file,
            }

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        error = f"timeout after {job.timeout_seconds}s"
        elog.record_result(log_path, job.name, "FAILED", duration, error=error)
        return {
            "job": job.name,
            "status": "FAILED",
            "duration_seconds": duration,
            "message": error,
            "report_file": None,
        }

    except Exception as e:
        duration = time.monotonic() - start
        elog.record_result(log_path, job.name, "FAILED", duration, error=str(e))
        return {
            "job": job.name,
            "status": "FAILED",
            "duration_seconds": duration,
            "message": str(e),
            "report_file": None,
        }


def run_all(
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    log_path: Path = EXECUTION_LOG_PATH,
) -> list[dict]:
    results = []
    for job in config.jobs:
        if not job.enabled:
            results.append({
                "job": job.name,
                "status": "SKIPPED",
                "duration_seconds": 0.0,
                "message": "job disabled (enabled: false)",
                "report_file": None,
            })
            continue
        results.append(run_job(job, log_path, dry_run=dry_run, force=force))
    return results


if __name__ == "__main__":
    import sys
    from .config import load_config

    dry_run = "--run" not in sys.argv
    force   = "--force" in sys.argv

    config = load_config("jobs.yaml")

    print(f"mode: {'dry-run' if dry_run else 'LIVE'} | force: {force}")
    print(f"jobs loaded: {[j.name for j in config.jobs]}\n")

    results = run_all(config, dry_run=dry_run, force=force)

    for r in results:
        dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "-"
        print(f"  {r['status']:<10}  {r['job']:<20}  {dur}  {r['message']}")