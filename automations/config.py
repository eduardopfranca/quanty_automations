"""
config.py
Loads and validates configuration: secrets/globals from .env, jobs from jobs.yaml.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Orchestrator"
    python_exe: str = sys.executable

    sender_email: str | None = None
    recipients: list[str] = Field(default_factory=list)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_on_success: bool = True


DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class ScheduleConfig(BaseModel):
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    min_interval_hours: float | None = None

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, v):
        if v is None:
            return v
        bad = [d for d in v if d.lower() not in DAYS]
        if bad:
            raise ValueError(f"invalid days: {bad}. Use {sorted(DAYS)}")
        return [d.lower() for d in v]

    @field_validator("day_of_month")
    @classmethod
    def _check_dom(cls, v):
        if v is not None and not (1 <= v <= 31):
            raise ValueError("day_of_month must be between 1 and 31")
        return v


class ResultConfig(BaseModel):
    success_marker: str | None = None
    failure_marker: str | None = None
    report_file: str | None = None


class JobConfig(BaseModel):
    name: str
    description: str = ""
    script: str
    python: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    timeout_seconds: int = 3600
    enabled: bool = True
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    result: ResultConfig = Field(default_factory=ResultConfig)


@dataclass
class Config:
    settings: Settings
    jobs: list[JobConfig]


def load_config(jobs_file: str | Path = "jobs.yaml") -> Config:
    settings = Settings()

    path = Path(jobs_file)
    if not path.exists():
        raise FileNotFoundError(f"jobs file not found: {path}")

    raw = os.path.expandvars(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(raw) or {}
    jobs = [JobConfig(**j) for j in data.get("jobs", [])]

    for job in jobs:
        if job.python is None:
            job.python = settings.python_exe

    names = [j.name for j in jobs]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate job names: {dupes}")

    return Config(settings=settings, jobs=jobs)