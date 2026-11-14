"""Auditoría de ejecuciones (ops.EtlExecution / ops.EtlStepLog) y watermarks (ops.Watermark)."""
from __future__ import annotations

import logging
from datetime import datetime

from common import config, db

log = logging.getLogger("etl")


class Audit:
    def __init__(self, pipeline: str, mode: str, triggered_by: str):
        self.cn = db.connect(config.DB_DW)
        cur = self.cn.cursor()
        # Ejecuciones que quedaron 'running' por un corte abrupto (proceso terminado) se cierran como fallidas
        cur.execute("UPDATE ops.EtlExecution SET Status = 'failed', EndTime = SYSDATETIME(),"
                    " ErrorDetail = 'Ejecución abandonada (proceso interrumpido); marcada al iniciar una nueva'"
                    " WHERE Status = 'running' AND StartTime < DATEADD(MINUTE, -30, SYSDATETIME())")
        cur.execute("SET NOCOUNT ON; INSERT ops.EtlExecution (PipelineName, Mode, TriggeredBy) VALUES (?, ?, ?);"
                    "SELECT CAST(SCOPE_IDENTITY() AS int);", pipeline, mode, triggered_by)
        self.execution_id: int = cur.fetchone()[0]
        self.pending_watermarks: dict[str, tuple[str, datetime]] = {}
        log.info("Ejecución %s iniciada (%s, %s)", self.execution_id, pipeline, mode)

    # ------------------------------------------------------------------ steps
    def step(self, name: str, source: str | None = None, target: str | None = None, **counts) -> None:
        """Registra un paso terminado. counts: rows_read, inserted, updated, rejected, wm_start, wm_end, start, status, error."""
        self.cn.cursor().execute(
            "INSERT ops.EtlStepLog (ExecutionID, StepName, SourceObject, TargetObject, RowsRead, RowsInserted, RowsUpdated,"
            " RowsRejected, WatermarkStart, WatermarkEnd, StartTime, EndTime, Status, ErrorDetail)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,SYSDATETIME(),?,?)",
            self.execution_id, name, source, target, counts.get("rows_read"), counts.get("inserted"),
            counts.get("updated"), counts.get("rejected"), counts.get("wm_start"), counts.get("wm_end"),
            counts.get("start") or datetime.now(), counts.get("status", "success"), counts.get("error"))

    # -------------------------------------------------------------- watermarks
    def get_watermark(self, source_object: str) -> datetime | None:
        return db.scalar(self.cn, "SELECT WatermarkValue FROM ops.Watermark WHERE SourceObject = ?", [source_object])

    def stage_watermark(self, source_object: str, column: str, value: datetime) -> None:
        """El watermark NO se persiste hasta que toda la ejecución termina con éxito."""
        self.pending_watermarks[source_object] = (column, value)

    def commit_watermarks(self) -> None:
        cur = self.cn.cursor()
        for obj, (col, value) in self.pending_watermarks.items():
            cur.execute(
                "MERGE ops.Watermark AS t USING (SELECT ? AS SourceObject, ? AS WatermarkColumn, ? AS WatermarkValue) AS s"
                " ON t.SourceObject = s.SourceObject"
                " WHEN MATCHED THEN UPDATE SET WatermarkValue = s.WatermarkValue, WatermarkColumn = s.WatermarkColumn,"
                "   ExecutionID = ?, UpdatedAt = SYSDATETIME()"
                " WHEN NOT MATCHED THEN INSERT (SourceObject, WatermarkColumn, WatermarkValue, ExecutionID)"
                "   VALUES (s.SourceObject, s.WatermarkColumn, s.WatermarkValue, ?);",
                obj, col, value, self.execution_id, self.execution_id)

    # -------------------------------------------------------------- cierre
    def finish(self, status: str, error: str | None = None) -> None:
        self.cn.cursor().execute(
            "UPDATE ops.EtlExecution SET EndTime = SYSDATETIME(), Status = ?, ErrorDetail = ? WHERE ExecutionID = ?",
            status, error, self.execution_id)
        log.info("Ejecución %s finalizada: %s", self.execution_id, status)
        self.cn.close()
