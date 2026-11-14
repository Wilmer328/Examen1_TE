"""raw -> clean: deduplicación con regla de supervivencia, reglas de calidad (cuarentena),
estandarización y upsert idempotente (MERGE). Todo set-based en SQL Server, en un solo batch
por entidad para que las tablas temporales vivan en la misma sesión.

El execution_id se interpola como entero (proviene de IDENTITY, no de entrada de usuario)."""
from __future__ import annotations

import logging
from datetime import datetime

from common import config, db
from etl.audit import Audit
from etl.catalog import Entity

log = logging.getLogger("etl")


def build_clean_sql(e: Entity, execution_id: int) -> str:
    eid = int(execution_id)
    raw_cols = ", ".join(f"r.{c}" for c in e.columns)
    # Columnas destino = columnas extraídas + columnas derivadas (p. ej. banderas de imputación)
    out_cols = list(e.columns) + [c for c in e.transforms if c not in e.columns]
    select_exprs = ", ".join(f"{e.transforms.get(c, 's.' + c)} AS {c}" for c in out_cols)
    upd_set = ", ".join(f"t.{c} = s.{c}" for c in out_cols if c != e.key)
    cmp_src = ", ".join(f"s.{c}" for c in out_cols if c != e.key)
    cmp_tgt = ", ".join(f"t.{c}" for c in out_cols if c != e.key)
    ins_cols = ", ".join(out_cols)
    ins_vals = ", ".join(f"s.{c}" for c in out_cols)

    rules_sql = []
    for r in e.reject_rules:
        desc = r.description.replace("'", "''")
        rules_sql.append(f"""
INSERT quarantine.RejectedRecord (ExecutionID, SourceObject, BusinessKey, RuleID, RuleDescription, Detail, RecordJson)
SELECT {eid}, '{e.source}', CAST(s.{e.key} AS nvarchar(100)), '{r.rule_id}', N'{desc}', N'{r.dimension}',
       (SELECT s2.* FROM #batch s2 WHERE s2._raw_id = s._raw_id FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
FROM #batch s WHERE {r.predicate}
  AND NOT EXISTS (SELECT 1 FROM quarantine.RejectedRecord q WHERE q.SourceObject = '{e.source}' AND q.Status = 'pendiente'
                  AND q.RuleID = '{r.rule_id}' AND q.BusinessKey = CAST(s.{e.key} AS nvarchar(100)));
SET @rejected += @@ROWCOUNT;
DELETE s FROM #batch s WHERE {r.predicate};""")

    outlier_decl = ""
    if "@qty_outlier" in select_exprs:
        # Outlier estadístico: media + 4 desviaciones estándar de las cantidades válidas, calculado UNA vez
        # (primera carga) y persistido en clean.QualityParameter. Solo se MARCA, no se elimina.
        outlier_decl = f"""
IF NOT EXISTS (SELECT 1 FROM clean.QualityParameter WHERE ParameterName = 'InvoiceLines.QuantityOutlierThreshold')
    INSERT clean.QualityParameter (ParameterName, ParameterValue, Method, ExecutionID)
    SELECT 'InvoiceLines.QuantityOutlierThreshold', ISNULL(AVG(CAST(Quantity AS float)) + 4 * STDEV(Quantity), 1000),
           'media + 4 desviaciones estándar de Quantity > 0 en la carga inicial', {eid}
    FROM #batch WHERE Quantity > 0;
DECLARE @qty_outlier decimal(18,2) = (SELECT ParameterValue FROM clean.QualityParameter
                                      WHERE ParameterName = 'InvoiceLines.QuantityOutlierThreshold');"""

    return f"""
SET NOCOUNT ON; SET XACT_ABORT ON;
DECLARE @read int, @dups int, @rejected int = 0, @ins int = 0, @upd int = 0;
-- Lote = filas raw de esta ejecución + último raw de las claves en cuarentena pendientes (registros tardíos)
SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.{e.key} ORDER BY x.{e.watermark} DESC, x._raw_id DESC) AS _rn
INTO #all
FROM (
    SELECT r._raw_id, {raw_cols} FROM raw.{e.name} r WHERE r._execution_id = {eid}
    UNION ALL
    SELECT r._raw_id, {raw_cols}
    FROM (SELECT DISTINCT BusinessKey FROM quarantine.RejectedRecord
          WHERE SourceObject = '{e.source}' AND Status = 'pendiente') q
    CROSS APPLY (SELECT TOP (1) * FROM raw.{e.name} r0
                 WHERE r0.{e.key} = TRY_CAST(q.BusinessKey AS int) ORDER BY r0._raw_id DESC) r
    WHERE r._execution_id <> {eid}
) x;
SET @read = @@ROWCOUNT;
SELECT * INTO #batch FROM #all WHERE _rn = 1;      -- regla de supervivencia: último watermark, último _raw_id
SET @dups = @read - @@ROWCOUNT;
{outlier_decl}

BEGIN TRAN;
-- Reglas de rechazo: un registro que vuelve a fallar la misma regla no se duplica en cuarentena
{''.join(rules_sql)}
-- Claves pendientes que ahora pasan todas las reglas se cierran como 'reprocesado'
UPDATE q SET Status = 'reprocesado' FROM quarantine.RejectedRecord q
WHERE q.SourceObject = '{e.source}' AND q.Status = 'pendiente'
  AND q.BusinessKey IN (SELECT CAST({e.key} AS nvarchar(100)) FROM #batch);

DECLARE @a TABLE (act nvarchar(10));
MERGE clean.{e.name} AS t
USING (SELECT {select_exprs} FROM #batch s) AS s
ON t.{e.key} = s.{e.key}
WHEN MATCHED AND EXISTS (SELECT {cmp_src} EXCEPT SELECT {cmp_tgt})
    THEN UPDATE SET {upd_set}, t._execution_id = {eid}, t._updated_at = SYSDATETIME()
WHEN NOT MATCHED BY TARGET
    THEN INSERT ({ins_cols}, _execution_id) VALUES ({ins_vals}, {eid})
OUTPUT $action INTO @a;
SELECT @ins = ISNULL(SUM(IIF(act = 'INSERT', 1, 0)), 0), @upd = ISNULL(SUM(IIF(act = 'UPDATE', 1, 0)), 0) FROM @a;
COMMIT;

SELECT @read AS rows_read, @dups AS duplicates, @rejected AS rejected, @ins AS inserted, @upd AS updated;
"""


def clean_entity(e: Entity, audit: Audit) -> dict:
    start = datetime.now()
    with db.connection(config.DB_STAGING) as cn:
        cur = cn.cursor()
        cur.execute(build_clean_sql(e, audit.execution_id))
        res = db.last_result(cur) or {}
    audit.step(f"clean:{e.name}", f"{config.DB_STAGING}.raw.{e.name}", f"{config.DB_STAGING}.clean.{e.name}",
               rows_read=res.get("rows_read"), inserted=res.get("inserted"), updated=res.get("updated"),
               rejected=res.get("rejected"), start=start)
    log.info("clean   %-22s leídas=%7s dup=%5s rechazadas=%5s ins=%7s upd=%7s", e.name, res.get("rows_read"),
             res.get("duplicates"), res.get("rejected"), res.get("inserted"), res.get("updated"))
    res["entity"] = e.name
    return res
