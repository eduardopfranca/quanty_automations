"""
cli.py
Ponto de entrada. Comandos: validate, run.
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERRO] config invalida: {e}")
        return 1

    s = config.settings
    print(f"app_name : {s.app_name}")
    print(f"python   : {s.python_exe}")
    print(f"jobs     : {len(config.jobs)}\n")

    for j in config.jobs:
        estado = "on" if j.enabled else "off"
        print(f"  - {j.name} [{estado}] -> {j.script}")
        sc = j.schedule
        partes = []
        if sc.days_of_week:
            partes.append(f"dias={','.join(sc.days_of_week)}")
        if sc.day_of_month:
            partes.append(f"dia_mes={sc.day_of_month}")
        if sc.min_interval_hours is not None:
            partes.append(f"intervalo>={sc.min_interval_hours}h")
        if partes:
            print(f"      schedule: {' | '.join(partes)}")

    print("\n[OK] config valida.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"[ERRO] config invalida: {e}")
        return 1

    from .runner import EXECUTION_LOG_PATH, run_all, run_job

    if args.job:
        job = next((j for j in config.jobs if j.name == args.job), None)
        if not job:
            names = [j.name for j in config.jobs]
            print(f"[ERRO] job '{args.job}' nao encontrado. Disponiveis: {names}")
            return 1
        results = [run_job(job, EXECUTION_LOG_PATH, dry_run=args.dry_run, force=args.force)]
    else:
        results = run_all(config, dry_run=args.dry_run, force=args.force)

    modo = "DRY-RUN" if args.dry_run else "EXECUCAO"
    print(f"\n{modo} — {len(results)} job(s)\n")

    icons = {"SUCCESS": "v", "FAILED": "X", "SKIPPED": "-", "DRY_RUN": "o"}
    failed = 0
    for r in results:
        icon = icons.get(r["status"], "?")
        dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "-"
        print(f"  [{icon}] {r['status']:<10}  {r['job']:<20}  {dur:>7}  {r['message']}")
        if r["status"] == "FAILED":
            failed += 1

    print()
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="automate", description="Orquestrador de jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="valida .env + jobs.yaml")
    p_val.add_argument("--config", default="jobs.yaml")
    p_val.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="executa uma rodada de jobs")
    p_run.add_argument("--config", default="jobs.yaml")
    p_run.add_argument("--dry-run", action="store_true", help="simula sem executar")
    p_run.add_argument("--force", action="store_true", help="ignora intervalos")
    p_run.add_argument("--job", default=None, metavar="NOME", help="roda apenas este job")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("schedule", help="(fase 3) loop agendado")

    args = parser.parse_args()
    if not hasattr(args, "func"):
        print(f"comando '{args.command}' ainda nao implementado.")
        sys.exit(2)
    sys.exit(args.func(args))