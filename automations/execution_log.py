"""
execution_log.py
----------------
Gerencia o arquivo execution_log.json que registra:
  - ultima execucao bem-sucedida de cada job
  - ultima tentativa (sucesso ou falha)
  - historico resumido dos ultimos N resultados

Formato do JSON:
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

# Maximo de entradas no historico por job (evita crescimento infinito)
MAX_HISTORY_ENTRIES = 30


def _load_raw(log_path: Path) -> dict:
    """Carrega o JSON do disco. Retorna dict vazio se nao existir."""
    if not log_path.exists():
        return {}
    try:
        text = log_path.read_text(encoding="utf-8")
        return json.loads(text) if text.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict, log_path: Path) -> None:
    """Salva o dict no disco como JSON identado."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def get_last_success(log_path: Path, job_name: str) -> datetime | None:
    """
    Retorna o datetime da ultima execucao bem-sucedida do job,
    ou None se nunca rodou com sucesso.
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
    Retorna um dict com info da ultima tentativa:
    {
        "timestamp": datetime,
        "status": "SUCCESS" | "FAILED" | "SKIPPED",
        "error": str | None,
        "duration_seconds": float
    }
    Retorna None se nunca tentou.
    """
    data = _load_raw(log_path)
    job_data = data.get(job_name)
    if not job_data or not job_data.get("last_attempt"):
        return None
    return {
        "timestamp": job_data.get("last_attempt"),
        "status": job_data.get("last_status"),
        "error": job_data.get("last_error"),
        "duration_seconds": job_data.get("last_duration_seconds"),
    }


def get_all_jobs_summary(log_path: Path) -> dict:
    """
    Retorna um resumo de todos os jobs registrados.
    {
        "job_name": {
            "last_success": "...",
            "last_status": "...",
            "last_attempt": "...",
        },
        ...
    }
    """
    data = _load_raw(log_path)
    summary = {}
    for job_name, job_data in data.items():
        summary[job_name] = {
            "last_success": job_data.get("last_success"),
            "last_status": job_data.get("last_status"),
            "last_attempt": job_data.get("last_attempt"),
            "last_duration_seconds": job_data.get("last_duration_seconds"),
            "last_error": job_data.get("last_error"),
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
    Registra o resultado de uma execucao (ou tentativa) de um job.

    Parametros:
        log_path:          caminho do execution_log.json
        job_name:          nome do job (ex: "factor_db")
        status:            "SUCCESS", "FAILED", ou "SKIPPED"
        duration_seconds:  tempo de execucao em segundos
        error:             mensagem de erro (se houver)
    """
    data = _load_raw(log_path)

    now_iso = datetime.now().isoformat(timespec="seconds")

    if job_name not in data:
        data[job_name] = {
            "last_success": None,
            "last_attempt": None,
            "last_status": None,
            "last_error": None,
            "last_duration_seconds": None,
            "history": [],
        }

    job_data = data[job_name]

    # Atualiza campos de ultima tentativa
    job_data["last_attempt"] = now_iso
    job_data["last_status"] = status
    job_data["last_error"] = error
    job_data["last_duration_seconds"] = round(duration_seconds, 2)

    # Se sucesso, atualiza last_success
    if status == "SUCCESS":
        job_data["last_success"] = now_iso

    # Adiciona ao historico
    entry = {
        "timestamp": now_iso,
        "status": status,
        "duration_seconds": round(duration_seconds, 2),
        "error": error,
    }
    job_data["history"].append(entry)

    # Limita tamanho do historico
    if len(job_data["history"]) > MAX_HISTORY_ENTRIES:
        job_data["history"] = job_data["history"][-MAX_HISTORY_ENTRIES:]

    _save_raw(data, log_path)