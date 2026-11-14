"""Métricas de calidad por dimensión (ops.DataQualityResult) después de cada carga."""
from __future__ import annotations

import logging

from common import config, db
from etl.audit import Audit

log = logging.getLogger("etl")

# (dimensión, objeto, regla, descripción, SQL que devuelve un valor, umbral, comparador)
CHECKS = [
    ("Completitud", "clean.Customers", "DQ-01", "% clientes con nombre, categoría y ciudad",
     "SELECT 100.0 * SUM(IIF(CustomerName IS NOT NULL AND CustomerCategoryID IS NOT NULL AND DeliveryCityID IS NOT NULL,1,0))"
     " / NULLIF(COUNT(*),0) FROM WWI_Staging.clean.Customers", 100, ">="),
    ("Completitud", "clean.InvoiceLines", "DQ-02", "% líneas con precio unitario original (no derivado)",
     "SELECT 100.0 * SUM(IIF(IsUnitPriceDerived = 0,1,0)) / NULLIF(COUNT(*),0) FROM WWI_Staging.clean.InvoiceLines", 99, ">="),
    ("Unicidad", "dw.FactSales", "DQ-03", "Claves InvoiceLineID duplicadas en el DW",
     "SELECT COUNT(*) FROM (SELECT InvoiceLineID FROM dw.FactSales GROUP BY InvoiceLineID HAVING COUNT(*) > 1) x", 0, "<="),
    ("Unicidad", "dw.DimCustomer", "DQ-04", "Clientes con más de una versión vigente (SCD2)",
     "SELECT COUNT(*) FROM (SELECT CustomerID FROM dw.DimCustomer WHERE IsCurrent = 1 GROUP BY CustomerID HAVING COUNT(*) > 1) x", 0, "<="),
    ("Validez", "dw.FactSales", "DQ-05", "Líneas con cantidad o importe neto no positivo",
     "SELECT COUNT(*) FROM dw.FactSales WHERE Quantity <= 0 OR NetAmount <= 0", 0, "<="),
    ("Consistencia", "dw.FactSales", "DQ-06", "% líneas donde Gross = Net + Tax",
     "SELECT 100.0 * SUM(IIF(ABS(GrossAmount - NetAmount - TaxAmount) <= 0.01,1,0)) / NULLIF(COUNT(*),0) FROM dw.FactSales", 100, ">="),
    ("Integridad", "dw.FactSales", "DQ-07", "Hechos asignados a miembro desconocido (-1)",
     "SELECT COUNT(*) FROM dw.FactSales WHERE CustomerKey = -1 OR ProductKey = -1 OR EmployeeKey = -1 OR GeographyKey = -1", 0, "<="),
    ("Integridad", "quarantine", "DQ-08", "Registros pendientes en cuarentena",
     "SELECT COUNT(*) FROM WWI_Staging.quarantine.RejectedRecord WHERE Status = 'pendiente'", 0, "<="),
    ("Oportunidad", "dw.FactSales", "DQ-09", "Minutos entre la ejecución y la disponibilidad en el DW (esta carga)",
     "SELECT DATEDIFF(MINUTE, (SELECT StartTime FROM ops.EtlExecution WHERE ExecutionID = {eid}), SYSDATETIME())", 15, "<="),
]


def run_quality_checks(audit: Audit) -> list[dict]:
    results = []
    with db.connection(config.DB_DW) as cn:
        cur = cn.cursor()
        for dim, obj, rule, desc, sql, thr, op in CHECKS:
            value = db.scalar(cn, sql.replace("{eid}", str(int(audit.execution_id))))
            value = float(value) if value is not None else None
            passed = value is not None and (value >= thr if op == ">=" else value <= thr)
            cur.execute("INSERT ops.DataQualityResult (ExecutionID, QualityDimension, ObjectName, RuleID, Description,"
                        " MetricValue, Threshold, Passed) VALUES (?,?,?,?,?,?,?,?)",
                        audit.execution_id, dim, obj, rule, desc, value, thr, int(passed))
            results.append({"rule": rule, "dimension": dim, "value": value, "threshold": thr, "passed": passed})
            log.info("calidad %-6s %-12s %-55s valor=%s umbral%s%s %s", rule, dim, desc, value, op, thr,
                     "OK" if passed else "REVISAR")
    return results
