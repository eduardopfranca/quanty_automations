# Architecture

## Overview

`quanty_automations` is a file-driven orchestrator. A single `automate run` command reads job definitions from `jobs.yaml`, checks eligibility for each job, executes eligible ones via subprocess, and records every result to `logs/execution_log.json`.

There is no daemon, no database, and no code to write per job.

---

## Decision flow

```
automate run
    │
    ├── load config (jobs.yaml + .env)
    │
    └── for each job:
          │
          ├── enabled: false?  → SKIPPED
          │
          ├── --force?         → RUN
          │
          ├── days_of_week set and today not in list?  → SKIPPED
          │
          ├── day_of_month set and today != value?     → SKIPPED
          │
          ├── min_interval_hours set?
          │     ├── never ran successfully?            → RUN
          │     ├── hours since last success < min?    → SKIPPED
          │     └── hours since last success >= min?   → RUN
          │
          └── execute via subprocess
                ├── exit code 0   → SUCCESS
                ├── exit code != 0 → FAILED
                └── timeout        → FAILED
```

---

## Modules

### `cli.py`
Entry point for the `automate` command. Parses arguments, loads config, calls `runner.run_all` or `runner.run_job`, and prints results. Does not contain business logic.

### `config.py`
Two responsibilities:
- `Settings`: reads `.env` via pydantic-settings (app name, python executable, SMTP credentials)
- `JobConfig` / `ScheduleConfig` / `ResultConfig`: validates `jobs.yaml` via pydantic
- `load_config(path)`: loads and cross-validates both sources, resolves `python` fallback

### `runner.py`
Core logic. Three functions:
- `_is_eligible(job, log_path, force)`: returns `(bool, reason)` — checks day, interval, force flag
- `run_job(job, log_path, dry_run, force)`: executes one job, records result, returns status dict
- `run_all(config, dry_run, force)`: iterates all enabled jobs, calls `run_job` for each

### `execution_log.py`
Reads and writes `logs/execution_log.json`. Stateless functions — no class, no global state.
Key functions:
- `get_last_success(log_path, job_name)`: returns `datetime | None`
- `record_result(log_path, job_name, status, duration, error)`: writes result, rotates history

---

## File layout

```
automations/          ← Python package
    cli.py
    config.py
    runner.py
    notifier.py
    execution_log.py

logs/                 ← created automatically on first run (gitignored)
    execution_log.json

examples/             ← standalone scripts for testing
    hello_job.py

setup_scheduler.py    ← run once as Admin to configure Windows Task Scheduler
    reads SCHEDULE_TIMES, TASK_NAME_PREFIX, SCHEDULE_DAILY from .env
    removes all existing tasks with the prefix before recreating
```

---

## Key design decisions

**Scripts run as subprocesses, not imports.**
Job scripts are called with `subprocess.run([python, script] + args)`. They don't know about the orchestrator and can be run manually without side effects. Exit code 0 = success.

**Scheduling state lives in a JSON file, not in memory.**
`execution_log.json` persists between runs. This means the orchestrator can be called multiple times per day (e.g. by Task Scheduler at 09:00 and 13:00) and each job only runs when its interval has genuinely elapsed.

**`logs/` is always relative to cwd.**
Wherever `automate run` is called from, `logs/` is created there. This keeps the project self-contained and avoids hardcoded paths.

**No wrappers, no per-job boilerplate.**
The previous system required a `jobs/xxx_job.py` wrapper for every script. Here, everything lives in `jobs.yaml`. Adding a job means editing one file.
