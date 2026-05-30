"""
setup_scheduler.py
Configures Windows Task Scheduler to run automate run
at the times defined in SCHEDULE_TIMES in .env.

Run ONCE as Administrator:
    python setup_scheduler.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

from automations.config import Settings

WORK_DIR = Path(__file__).resolve().parent


def check_admin():
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("ERROR: run this script as Administrator.")
        print("Right-click terminal > 'Run as administrator'")
        sys.exit(1)


def remove_all_tasks(prefix: str):
    result = subprocess.run(
        ["schtasks", "/Query", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        # if f'"{prefix}' in line or f",{prefix}" in line:
        if prefix in line:
            # task_name = line.split(",")[0].strip().strip('"').lstrip("\\")
            task_name = line.split(",")[0].strip().strip('"')
            subprocess.run(
                ["schtasks", "/Delete", "/TN", task_name, "/F"],
                capture_output=True, text=True,
            )
            print(f"  removed: {task_name}")


def create_task(task_name: str, time: str, automate_exe: str, daily: bool = True) -> bool:
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'"{automate_exe}" run',
        "/SC", "DAILY" if daily else "WEEKLY",
        "/ST", time,
        "/RL", "HIGHEST",
        "/F",
    ]
    if not daily:
        cmd += ["/D", "MON,TUE,WED,THU,FRI"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR creating {task_name}: {result.stderr}")
        return False

    print(f"  created: {task_name} -> {time} ({'daily' if daily else 'mon-fri'})")

    ps_cmd = (
        f'$t = Get-ScheduledTask -TaskName "{task_name}"; '
        f'$t.Actions[0].WorkingDirectory = "{WORK_DIR}"; '
        f'$t.Settings.StartWhenAvailable = $true; '
        f'Set-ScheduledTask -InputObject $t'
    )
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  WorkingDirectory + StartWhenAvailable set for {task_name}")
    else:
        print(f"  WARNING: could not set WorkingDirectory/StartWhenAvailable: {result.stderr.strip()}")

    return True


def verify_task(task_name: str):
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and ":" in line:
                print(f"    {line}")
    else:
        print(f"    ERROR querying: {result.stderr.strip()}")


def main():
    print("=" * 60)
    print("  TASK SCHEDULER SETUP — quanty_automations")
    print("=" * 60)

    check_admin()

    settings = Settings()

    print(f"\n[0/4] Locating automate executable...")
    automate_exe = shutil.which("automate")
    if not automate_exe:
        print("  ERROR: 'automate' not found. Run: pip install -e .")
        sys.exit(1)
    print(f"  automate       : {automate_exe}")
    print(f"  work dir       : {WORK_DIR}")
    print(f"  task prefix    : {settings.task_name_prefix}")
    print(f"  schedule times : {settings.schedule_times}")
    print(f"  daily mode     : {settings.schedule_daily}")

    print(f"\n[1/4] Removing existing tasks with prefix '{settings.task_name_prefix}'...")
    remove_all_tasks(settings.task_name_prefix)

    print(f"\n[2/4] Creating tasks...")
    all_ok = True
    created = []
    for time in settings.schedule_times:
        task_name = f"{settings.task_name_prefix}_{time.replace(':', '')}"
        ok = create_task(task_name, time, automate_exe, daily=settings.schedule_daily)
        if ok:
            created.append(task_name)
        else:
            all_ok = False

    print(f"\n[3/4] Verifying tasks...")
    for task_name in created:
        print(f"\n  {task_name}:")
        verify_task(task_name)

    print(f"\n{'=' * 60}")
    if all_ok:
        print("  DONE. Tasks created successfully.")
    else:
        print("  WARNING: some tasks failed. Check errors above.")

    print(f"\n  Schedule:")
    for time in settings.schedule_times:
        print(f"    - {time} ({'daily' if settings.schedule_daily else 'mon-fri'})")
    print(f"\n  Command : automate run")
    print(f"  Work dir: {WORK_DIR}")
    print(f"\n  To test manually:")
    print(f"    automate run --dry-run")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()