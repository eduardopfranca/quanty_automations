# Jobs Reference

Complete reference for configuring `jobs.yaml`.

---

## Top-level structure

```yaml
jobs:
  - name: ...
  - name: ...
```

Each entry under `jobs` is one job. Job names must be unique.

---

## Job fields

### `name` *(required)*
Unique identifier for the job. Used in CLI (`--job <name>`), logs, and `execution_log.json`.

```yaml
name: market_data
```

---

### `script` *(required)*
Path to the Python script to run. Relative to the directory where `automate` is called.

```yaml
script: src/utils/market_data_updater.py
```

---

### `description`
Human-readable description. Shown in `automate validate`. No effect on execution.

```yaml
description: Downloads futures and FX data via yfinance
```

---

### `python`
Path to the Python executable to use. Defaults to the same Python running the orchestrator.

```yaml
python: C:\Users\eduar\AppData\Local\Programs\Python\Python313\python.exe
```

---

### `args`
Extra command-line arguments passed to the script.

```yaml
args: [--force, --verbose]
```

---

### `cwd`
Working directory for the subprocess. Defaults to the directory where `automate` is called.

```yaml
cwd: C:\Users\eduar\code\my_project
```

---

### `timeout_seconds`
Maximum runtime in seconds before the job is killed and marked FAILED. Default: `3600` (1 hour).

```yaml
timeout_seconds: 1800  # 30 minutes
```

---

### `enabled`
Set to `false` to disable a job without removing it. Default: `true`.

```yaml
enabled: false
```

---

## `schedule` block

All schedule fields are optional. A job with no schedule runs every time `automate run` is called.

```yaml
schedule:
  days_of_week: [mon, tue, wed, thu, fri]
  day_of_month: 1
  min_interval_hours: 24
```

### `days_of_week`
List of days the job is allowed to run. Valid values: `mon tue wed thu fri sat sun`.
If today is not in the list, the job is skipped.

```yaml
schedule:
  days_of_week: [mon, wed, fri]
```

### `day_of_month`
Run only on this calendar day (1–31). If today is not this day, the job is skipped.

```yaml
schedule:
  day_of_month: 1   # first of every month
```

### `min_interval_hours`
Minimum hours between successful runs. The orchestrator checks `last_success` in `execution_log.json`.
If the elapsed time is less than this value, the job is skipped.

```yaml
schedule:
  min_interval_hours: 720   # roughly 30 days
```

---

## `result` block

Controls how the orchestrator interprets the script's output. Optional — exit code alone is usually enough.

```yaml
result:
  success_marker: "DONE"
  failure_marker: "CRITICAL ERROR"
```

### `success_marker`
If set, the script must both exit with code 0 **and** print this string to stdout.
Useful for scripts that always exit 0 but print a marker on success.

### `failure_marker`
If set and found in stdout, the job is marked FAILED even if exit code is 0.
Useful for scripts that swallow exceptions and print an error message instead of raising.

---

## Full example

```yaml
jobs:
  - name: factor_db
    description: Run factor_db notebook, zip output, upload to Drive
    script: src/utils/factor_db_runner.py
    timeout_seconds: 1800
    schedule:
      days_of_week: [mon, tue, wed, thu, fri]
      min_interval_hours: 20

  - name: market_data
    description: Download futures and FX history via yfinance
    script: src/utils/market_data_updater.py
    args: [--force]
    schedule:
      min_interval_hours: 360

  - name: code_backup
    description: Zip and upload code to personal Google Drive
    script: src/utils/code_backup.py
    timeout_seconds: 3600
    schedule:
      min_interval_hours: 48

  - name: database_backup
    description: Zip and upload data/ to personal Google Drive
    script: src/utils/database_backup.py
    timeout_seconds: 7200
    schedule:
      min_interval_hours: 720

  - name: hello
    description: Smoke test — always succeeds
    script: examples/hello_job.py
    enabled: false
```

---

## How success is determined

1. Script exits with code **0** → eligible for success
2. If `failure_marker` is set and found in stdout → **FAILED** regardless of exit code
3. If `success_marker` is set → must be present in stdout to be **SUCCESS**
4. If no markers are set → exit code 0 = **SUCCESS**, anything else = **FAILED**
