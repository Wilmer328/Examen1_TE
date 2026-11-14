"""Extracción fuente -> staging raw (append-only), inicial o incremental por watermark."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from common import config, db
from etl.audit import Audit
from etl.catalog import Entity

log = logging.getLogger("etl")


def extract_entity(entity: Entity, audit: Audit, mode: str) -> int:
    start = datetime.now()
    wm = None if mode == "initial" else audit.get_watermark(entity.source)
    cols = ", ".join(entity.columns)
    sql = f"SELECT {cols} FROM {entity.source}"
    params: list = []
    wm_from = None
    if wm is not None:
        # Ventana de solapamiento para registros que llegan tarde a la fuente.
        wm_from = wm - timedelta(minutes=config.EXTRACT_OVERLAP_MINUTES)
        sql += f" WHERE {entity.watermark} > ?"
        params.append(wm_from)

    insert = (f"INSERT {entity.raw_table} (_execution_id, {cols}) VALUES (?, {', '.join('?' * len(entity.columns))})")
    wm_idx = entity.columns.index(entity.watermark)
    total, max_wm = 0, wm

    with db.connection(config.DB_SOURCE) as src, db.connection(config.DB_STAGING, autocommit=False) as stg:
        cur = src.cursor()
        cur.execute(sql, params)
        while True:
            batch = cur.fetchmany(config.ETL_BATCH_SIZE)
            if not batch:
                break
            rows = [(audit.execution_id, *r) for r in batch]
            db.executemany(stg, insert, rows)
            total += len(rows)
            batch_max = max(r[wm_idx] for r in batch)
            max_wm = batch_max if max_wm is None or batch_max > max_wm else max_wm
        stg.commit()

    if max_wm is not None:
        audit.stage_watermark(entity.source, entity.watermark, max_wm)
    audit.step(f"extract:{entity.name}", entity.source, f"{config.DB_STAGING}.{entity.raw_table}",
               rows_read=total, inserted=total, wm_start=wm_from, wm_end=max_wm, start=start)
    log.info("extract %-22s filas=%7d  watermark %s -> %s", entity.name, total, wm_from, max_wm)
    return total
