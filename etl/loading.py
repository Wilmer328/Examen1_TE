"""clean/ready -> Data Warehouse mediante procedimientos almacenados idempotentes."""
from __future__ import annotations

import logging
from datetime import datetime

from common import config, db
from etl.audit import Audit

log = logging.getLogger("etl")

DIMENSION_STEPS = [
    ("dw.usp_LoadDimDate", "ready (calendario generado)", "dw.DimDate", False),
    ("dw.usp_LoadDimGeography", "ready.vw_Geography", "dw.DimGeography", True),
    ("dw.usp_LoadDimCustomer", "ready.vw_Customer", "dw.DimCustomer", True),
    ("dw.usp_LoadDimProduct", "ready.vw_Product", "dw.DimProduct", True),
    ("dw.usp_LoadDimEmployee", "ready.vw_Employee", "dw.DimEmployee", True),
]


def _run_proc(sql: str, params: list) -> dict:
    with db.connection(config.DB_DW) as cn:
        cur = cn.cursor()
        cur.execute(sql, params)
        return db.last_result(cur) or {}


def load_dimensions(audit: Audit) -> None:
    for proc, src, tgt, takes_exec in DIMENSION_STEPS:
        start = datetime.now()
        res = _run_proc(f"EXEC {proc} @ExecutionID = ?" if takes_exec else f"EXEC {proc}",
                        [audit.execution_id] if takes_exec else [])
        audit.step(f"load:{tgt}", f"{config.DB_STAGING}.{src}", f"{config.DB_DW}.{tgt}",
                   inserted=res.get("inserted") or 0, updated=res.get("updated") or 0, start=start)
        log.info("load    %-22s ins=%7s upd=%7s", tgt, res.get("inserted"), res.get("updated"))


def load_facts(audit: Audit, full_reload: bool) -> dict:
    start = datetime.now()
    res = _run_proc("EXEC dw.usp_LoadFactSales @ExecutionID = ?, @FullReload = ?", [audit.execution_id, int(full_reload)])
    audit.step("load:dw.FactSales", f"{config.DB_STAGING}.ready.vw_SalesLine", f"{config.DB_DW}.dw.FactSales",
               rows_read=res.get("rows_read"), inserted=res.get("inserted"), updated=res.get("updated"), start=start)
    log.info("load    %-22s leídas=%7s ins=%7s upd=%7s", "dw.FactSales", res.get("rows_read"), res.get("inserted"),
             res.get("updated"))
    return res


def reconcile(audit: Audit) -> list[dict]:
    start = datetime.now()
    with db.connection(config.DB_DW) as cn:
        cur = cn.cursor()
        cur.execute("EXEC ops.usp_Reconcile @ExecutionID = ?", audit.execution_id)
        while cur.description is None and cur.nextset():
            pass
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    by = {r["Layer"]: r for r in rows}
    src, clean, quar, dw = (by.get(k, {}).get("RowCountValue", 0) for k in ("1-fuente", "3-clean", "3b-cuarentena", "4-dw"))
    ok = (src == clean + quar) and (clean == dw)
    audit.step("reconcile:InvoiceLines", "fuente/raw/clean/cuarentena", "ops.Reconciliation",
               rows_read=src, inserted=dw, rejected=quar, start=start, status="success" if ok else "warning",
               error=None if ok else f"Diferencia: fuente={src} clean={clean} cuarentena={quar} dw={dw}")
    log.info("reconcile fuente=%s clean=%s cuarentena=%s dw=%s -> %s", src, clean, quar, dw, "OK" if ok else "DIFERENCIA")
    return rows
