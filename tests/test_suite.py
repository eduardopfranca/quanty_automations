"""
tests/test_suite.py
Automated tests for quanty_automations.
Run with: pytest
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from automations.config import JobConfig, ScheduleConfig, ResultConfig, load_config
from automations.execution_log import get_last_success, record_result, get_all_jobs_summary
from automations.runner import _is_eligible, run_job


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def make_job(name="test_job", script="examples/hello_job.py", **schedule_kwargs) -> JobConfig:
    job = JobConfig(
        name=name,
        script=script,
        schedule=ScheduleConfig(**schedule_kwargs),
        result=ResultConfig(),
    )
    job.python = "python"
    return job


# ═══════════════════════════════════════════════════════════
#  EXECUTION LOG
# ═══════════════════════════════════════════════════════════

class TestExecutionLog:

    def test_returns_none_if_never_ran(self, tmp_path):
        log = tmp_path / "execution_log.json"
        assert get_last_success(log, "my_job") is None

    def test_records_success_and_retrieves(self, tmp_path):
        log = tmp_path / "execution_log.json"
        record_result(log, "my_job", "SUCCESS", duration_seconds=5.0)
        result = get_last_success(log, "my_job")
        assert result is not None
        assert isinstance(result, datetime)

    def test_failed_does_not_update_last_success(self, tmp_path):
        log = tmp_path / "execution_log.json"
        record_result(log, "my_job", "FAILED", error="something went wrong")
        assert get_last_success(log, "my_job") is None

    def test_history_rotates_at_30_entries(self, tmp_path):
        log = tmp_path / "execution_log.json"
        for _ in range(35):
            record_result(log, "my_job", "SUCCESS", duration_seconds=1.0)
        data = json.loads(log.read_text(encoding="utf-8"))
        assert len(data["my_job"]["history"]) == 30

    def test_summary_contains_all_jobs(self, tmp_path):
        log = tmp_path / "execution_log.json"
        record_result(log, "job_a", "SUCCESS")
        record_result(log, "job_b", "FAILED", error="oops")
        summary = get_all_jobs_summary(log)
        assert "job_a" in summary
        assert "job_b" in summary

    def test_handles_corrupted_log(self, tmp_path):
        log = tmp_path / "execution_log.json"
        log.write_text("not valid json", encoding="utf-8")
        assert get_last_success(log, "my_job") is None


# ═══════════════════════════════════════════════════════════
#  ELIGIBILITY
# ═══════════════════════════════════════════════════════════

class TestEligibility:

    def test_no_schedule_is_always_eligible(self, tmp_path):
        log = tmp_path / "execution_log.json"
        job = make_job()
        eligible, _ = _is_eligible(job, log)
        assert eligible

    def test_force_overrides_everything(self, tmp_path):
        log = tmp_path / "execution_log.json"
        # record a very recent success
        record_result(log, "test_job", "SUCCESS")
        job = make_job(min_interval_hours=999)
        eligible, reason = _is_eligible(job, log, force=True)
        assert eligible
        assert reason == "forced"

    def test_skipped_when_interval_not_elapsed(self, tmp_path):
        log = tmp_path / "execution_log.json"
        record_result(log, "test_job", "SUCCESS")
        job = make_job(min_interval_hours=24)
        eligible, _ = _is_eligible(job, log)
        assert not eligible

    def test_eligible_when_interval_elapsed(self, tmp_path):
        log = tmp_path / "execution_log.json"
        # write a last_success 25 hours ago
        data = {
            "test_job": {
                "last_success": (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds"),
                "last_attempt": None,
                "last_status": "SUCCESS",
                "last_error": None,
                "last_duration_seconds": 1.0,
                "history": [],
            }
        }
        log.write_text(json.dumps(data), encoding="utf-8")
        job = make_job(min_interval_hours=24)
        eligible, _ = _is_eligible(job, log)
        assert eligible

    def test_eligible_when_never_ran(self, tmp_path):
        log = tmp_path / "execution_log.json"
        job = make_job(min_interval_hours=24)
        eligible, _ = _is_eligible(job, log)
        assert eligible

    def test_skipped_wrong_day(self, tmp_path):
        log = tmp_path / "execution_log.json"
        # force a day that is not today
        today = datetime.now().weekday()  # 0=mon ... 6=sun
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        other_days = [all_days[i] for i in range(7) if i != today]
        job = make_job(days_of_week=other_days)
        eligible, _ = _is_eligible(job, log)
        assert not eligible

    def test_eligible_correct_day(self, tmp_path):
        log = tmp_path / "execution_log.json"
        today = datetime.now().weekday()
        all_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        job = make_job(days_of_week=[all_days[today]])
        eligible, _ = _is_eligible(job, log)
        assert eligible


# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════

class TestConfig:

    def test_load_valid_config(self, tmp_path):
        yaml_content = """
jobs:
  - name: hello
    script: examples/hello_job.py
"""
        jobs_file = tmp_path / "jobs.yaml"
        jobs_file.write_text(yaml_content, encoding="utf-8")
        config = load_config(jobs_file)
        assert len(config.jobs) == 1
        assert config.jobs[0].name == "hello"

    def test_rejects_duplicate_job_names(self, tmp_path):
        yaml_content = """
jobs:
  - name: hello
    script: examples/hello_job.py
  - name: hello
    script: examples/hello_job.py
"""
        jobs_file = tmp_path / "jobs.yaml"
        jobs_file.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            load_config(jobs_file)

    def test_rejects_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_day_raises(self, tmp_path):
        yaml_content = """
jobs:
  - name: hello
    script: examples/hello_job.py
    schedule:
      days_of_week: [mon, xyz]
"""
        jobs_file = tmp_path / "jobs.yaml"
        jobs_file.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(Exception):
            load_config(jobs_file)

    def test_python_fallback_to_sys_executable(self, tmp_path):
        yaml_content = """
jobs:
  - name: hello
    script: examples/hello_job.py
"""
        jobs_file = tmp_path / "jobs.yaml"
        jobs_file.write_text(yaml_content, encoding="utf-8")
        config = load_config(jobs_file)
        assert config.jobs[0].python is not None


# ═══════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════

class TestRunner:

    def test_dry_run_does_not_record(self, tmp_path):
        log = tmp_path / "execution_log.json"
        job = make_job(script="examples/hello_job.py")
        result = run_job(job, log, dry_run=True)
        assert result["status"] == "DRY_RUN"
        assert not log.exists()

    def test_hello_job_succeeds(self, tmp_path):
        log = tmp_path / "execution_log.json"
        job = make_job(script="examples/hello_job.py")
        result = run_job(job, log)
        assert result["status"] == "SUCCESS"
        assert get_last_success(log, "test_job") is not None

    def test_missing_script_fails(self, tmp_path):
        log = tmp_path / "execution_log.json"
        job = make_job(script="nonexistent_script.py")
        result = run_job(job, log)
        assert result["status"] == "FAILED"

    def test_skipped_job_not_recorded_in_dry_run(self, tmp_path):
        log = tmp_path / "execution_log.json"
        record_result(log, "test_job", "SUCCESS")
        job = make_job(min_interval_hours=999)
        result = run_job(job, log, dry_run=True)
        assert result["status"] == "SKIPPED"