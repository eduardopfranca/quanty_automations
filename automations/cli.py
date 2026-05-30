"""
cli.py
Entry point. Commands: validate, run.
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERROR] invalid config: {e}")
        return 1

    s = config.settings
    print(f"app_name : {s.app_name}")
    print(f"python   : {s.python_exe}")
    print(f"jobs     : {len(config.jobs)}\n")

    for j in config.jobs:
        state = "on" if j.enabled else "off"
        print(f"  - {j.name} [{state}] -> {j.script}")
        sc = j.schedule
        parts = []
        if sc.days_of_week:
            parts.append(f"days={','.join(sc.days_of_week)}")
        if sc.day_of_month:
            parts.append(f"day_of_month={sc.day_of_month}")
        if sc.min_interval_hours is not None:
            parts.append(f"interval>={sc.min_interval_hours}h")
        if parts:
            print(f"      schedule: {' | '.join(parts)}")

    print("\n[OK] config valid.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERROR] invalid config: {e}")
        return 1

    from datetime import datetime
    from .notifier import send_summary
    from .runner import EXECUTION_LOG_PATH, run_all, run_job

    start = datetime.now()

    if args.job:
        job = next((j for j in config.jobs if j.name == args.job), None)
        if not job:
            names = [j.name for j in config.jobs]
            print(f"[ERROR] job '{args.job}' not found. Available: {names}")
            return 1
        results = [run_job(job, EXECUTION_LOG_PATH, dry_run=args.dry_run, force=args.force)]
    else:
        results = run_all(config, dry_run=args.dry_run, force=args.force)

    end = datetime.now()

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n{mode} — {len(results)} job(s)\n")

    icons = {"SUCCESS": "v", "FAILED": "X", "SKIPPED": "-", "DRY_RUN": "o"}
    failed = 0
    for r in results:
        icon = icons.get(r["status"], "?")
        dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "-"
        print(f"  [{icon}] {r['status']:<10}  {r['job']:<20}  {dur:>7}  {r['message']}")
        if r["status"] == "FAILED":
            failed += 1

    print()

    if not args.dry_run:
        try:
            send_summary(config.settings, results, start, end)
        except Exception as e:
            print(f"  [!] email not sent: {e}")

    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="automate", description="Job orchestrator.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="validate .env + jobs.yaml")
    p_val.add_argument("--config", default="jobs.yaml")
    p_val.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="run a round of jobs")
    p_run.add_argument("--config", default="jobs.yaml")
    p_run.add_argument("--dry-run", action="store_true", help="simulate without executing")
    p_run.add_argument("--force", action="store_true", help="ignore intervals")
    p_run.add_argument("--job", default=None, metavar="NAME", help="run only this job")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("schedule", help="(phase 3) scheduled loop")

    args = parser.parse_args()
    if not hasattr(args, "func"):
        print(f"command '{args.command}' not yet implemented.")
        sys.exit(2)
    sys.exit(args.func(args))