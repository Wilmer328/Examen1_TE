"""Orquestador del pipeline end-to-end.

Uso:
    python -m etl.pipeline                 # modo auto: inicial si no hay watermarks, si no incremental
    python -m etl.pipeline --mode initial  # extracción completa + recarga completa de hechos
    python -m etl.pipeline --fail-at load_facts   # falla controlada para probar recuperación

Orden: extracción (todas) -> limpieza (todas) -> dimensiones -> hechos -> reconciliación -> calidad
       -> commit de watermarks -> predicciones ML -> evaluación de alertas.
Reintentos: cada paso se reintenta ante errores transitorios de conexión (backoff exponencial).
Si la ejecución falla, los watermarks NO avanzan; re-ejecutar es seguro (idempotencia por MERGE).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import traceback

import pyodbc

from common import config, db
from etl import extraction, loading, quality, transformation
from etl.audit import Audit
from etl.catalog import ENTITIES

log = logging.getLogger("etl")
TRANSIENT = (pyodbc.OperationalError, pyodbc.InterfaceError)


class SimulatedFailure(RuntimeError):
    pass


def with_retry(name: str, fn, *args, fail_at: str | None = None, **kwargs):
    for attempt in range(1, config.ETL_MAX_RETRIES + 1):
        try:
            if fail_at == name:
                raise SimulatedFailure(f"Falla SIMULADA en el paso '{name}' (--fail-at)")
            return fn(*args, **kwargs)
        except TRANSIENT as exc:
            if attempt == config.ETL_MAX_RETRIES:
                raise
            wait = 2 ** attempt
            log.warning("Error transitorio en %s (intento %s/%s): %s. Reintento en %ss", name, attempt,
                        config.ETL_MAX_RETRIES, exc, wait)
            time.sleep(wait)


def detect_mode() -> str:
    with db.connection(config.DB_DW) as cn:
        n = db.scalar(cn, "SELECT COUNT(*) FROM ops.Watermark")
    return "initial" if not n else "incremental"


def run(mode: str = "auto", triggered_by: str = "manual", fail_at: str | None = None,
        post_steps: bool = True) -> int:
    mode = detect_mode() if mode == "auto" else mode
    audit = Audit("wwi_sales_pipeline", mode, triggered_by)
    try:
        for e in ENTITIES:
            with_retry("extract", extraction.extract_entity, e, audit, mode, fail_at=fail_at)
        for e in ENTITIES:
            with_retry("clean", transformation.clean_entity, e, audit, fail_at=fail_at)
        with_retry("load_dimensions", loading.load_dimensions, audit, fail_at=fail_at)
        with_retry("load_facts", loading.load_facts, audit, mode == "initial", fail_at=fail_at)
        with_retry("reconcile", loading.reconcile, audit, fail_at=fail_at)
        with_retry("quality", quality.run_quality_checks, audit, fail_at=fail_at)
        audit.commit_watermarks()
        audit.finish("success")
    except Exception as exc:  # noqa: BLE001 - se registra cualquier falla en la auditoría
        log.error("Pipeline falló: %s", exc)
        audit.step("pipeline", status="failed", error=traceback.format_exc()[-3500:])
        audit.finish("failed", str(exc)[:3500])
        return -audit.execution_id

    if post_steps:
        _post_load(audit.execution_id)
    return audit.execution_id


def _post_load(execution_id: int) -> None:
    """Automatización posterior a la carga: predicción batch y evaluación de alertas.
    Fallas aquí no invalidan la carga del DW (ya confirmada), pero se registran."""
    try:
        from machine_learning import predict
        predict.run_batch_prediction()
    except FileNotFoundError:
        log.warning("No hay modelo activo entrenado todavía; se omite la predicción batch.")
    except Exception as exc:  # noqa: BLE001
        log.error("Predicción batch falló: %s", exc)
    try:
        from notifications import alerts
        alerts.evaluate_and_notify(trigger=f"pipeline:{execution_id}")
    except Exception as exc:  # noqa: BLE001
        log.error("Evaluación de alertas falló: %s", exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(config.ROOT / "etl" / "logs" / "pipeline.log", encoding="utf-8")])
    p = argparse.ArgumentParser(description="Pipeline ETL WideWorldImporters -> Staging -> DW")
    p.add_argument("--mode", choices=["auto", "initial", "incremental"], default="auto")
    p.add_argument("--triggered-by", default="manual")
    p.add_argument("--fail-at", choices=["extract", "clean", "load_dimensions", "load_facts", "reconcile", "quality"])
    p.add_argument("--no-post", action="store_true", help="No ejecutar predicción ni alertas")
    a = p.parse_args()
    eid = run(a.mode, a.triggered_by, a.fail_at, not a.no_post)
    print(f"EXECUTION_ID={abs(eid)} STATUS={'success' if eid > 0 else 'failed'}")
    sys.exit(0 if eid > 0 else 1)


if __name__ == "__main__":
    main()
