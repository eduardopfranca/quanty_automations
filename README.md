# quanty_automations

A file-driven job orchestrator. Define jobs in `jobs.yaml`, secrets in `.env`. No boilerplate per job — just config.

## Quick start

```bash
pip install -e .
copy .env.example .env
copy jobs.example.yaml jobs.yaml
automate validate
```

## Commands

```bash
# Validate jobs.yaml and .env without running anything
automate validate

# Dry run — check eligibility without executing
automate run --dry-run

# Run all eligible jobs
automate run

# Run a single job by name
automate run --job <name>

# Force execution regardless of intervals
automate run --force

# Force a specific job
automate run --job <name> --force
```

## Adding a job

Add an entry to `jobs.yaml`:

```yaml
jobs:
  - name: my_job
    script: path/to/my_script.py
    schedule:
      days_of_week: [mon, tue, wed, thu, fri]
      min_interval_hours: 24
```

That's it. The orchestrator calls `python path/to/my_script.py` via subprocess.
Exit code 0 = success. Any other exit code = failure.

## Project structure

```
quanty_automations/
├── pyproject.toml
├── jobs.yaml              # your job definitions (not committed)
├── .env                   # your secrets (not committed)
├── jobs.example.yaml      # template to copy from
├── .env.example           # template to copy from
├── examples/
│   └── hello_job.py       # minimal example script
├── docs/
│   ├── ARCHITECTURE.md
│   └── JOBS_REFERENCE.md
└── automations/
    ├── cli.py             # entry point (automate command)
    ├── config.py          # settings + job model + loader
    ├── runner.py          # eligibility, subprocess, result recording
    └── execution_log.py   # reads and writes execution_log.json
```

## State and logs

After each run, results are persisted to `logs/execution_log.json` (created automatically).
This file tracks last success, last attempt, status, duration, and a rolling 30-entry history per job.
It is the single source of truth for scheduling decisions.

## Requirements

- Python 3.10+
- Dependencies: `pydantic>=2`, `pydantic-settings>=2`, `pyyaml>=6`
