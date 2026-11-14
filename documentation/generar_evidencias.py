"""Genera evidencias reproducibles en documentation/evidencias/ a partir de las bases reales:
  01_perfil_fuente.md        perfilado de columnas de la fuente (nulos, distintos, min, max, top valores)
  02_diccionario_fuente.md   diccionario de datos de las tablas fuente usadas (tipos, nulabilidad, PK/FK)
  03_diccionario_dw.md       diccionario del Data Warehouse (dw, ops, ml, ai)
  04_resultados_carga.md     ejecuciones ETL, pasos, reconciliación, calidad, cuarentena, SCD2
  05_validacion_kpis.md      KPIs de la API vs SQL independiente + tiempos de respuesta
Uso:  python -m documentation.generar_evidencias
"""
from __future__ import annotations

import time
from datetime import datetime

import pandas as pd

from common import analytics, config, db
from etl.catalog import ENTITIES

OUT = config.EVIDENCE_DIR


def md_table(df: pd.DataFrame, max_rows: int = 60) -> str:
    if df.empty:
        return "_(sin filas)_\n"
    df = df.head(max_rows).copy()
    df = df.apply(lambda c: c.map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v).replace("|", "\\|")[:80]))
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def header(title: str) -> str:
    return f"# {title}\n\nGenerado automáticamente el {datetime.now():%Y-%m-%d %H:%M} por `documentation/generar_evidencias.py`.\n\n"


def profile_source() -> None:
    parts = [header("Perfil de datos de la fuente (WideWorldImporters)")]
    with db.connection(config.DB_SOURCE) as cn:
        for e in ENTITIES:
            n = db.scalar(cn, f"SELECT COUNT(*) FROM {e.source}")
            rows = []
            for c in e.columns:
                v = f"CAST({c} AS int)" if c.startswith("Is") else c   # MIN/MAX no aceptan bit
                r = db.query_records(cn, f"SELECT SUM(IIF({c} IS NULL,1,0)) nulos, COUNT(DISTINCT {c}) distintos,"
                                         f" CAST(MIN({v}) AS nvarchar(60)) minimo, CAST(MAX({v}) AS nvarchar(60)) maximo FROM {e.source}")[0]
                top = db.query_records(cn, f"SELECT TOP 3 CAST({c} AS nvarchar(40)) v, COUNT(*) n FROM {e.source} GROUP BY {c} ORDER BY COUNT(*) DESC")
                rows.append({"columna": c, "% nulos": round(100 * (r["nulos"] or 0) / max(n, 1), 2), "distintos": r["distintos"],
                             "mín": r["minimo"], "máx": r["maximo"], "valores frecuentes": "; ".join(f"{t['v']} ({t['n']})" for t in top)})
            parts.append(f"## {e.source} — {n:,} filas\n\nClave: `{e.key}` · watermark: `{e.watermark}`\n\n{md_table(pd.DataFrame(rows))}\n")
        dup = db.scalar(cn, "SELECT COUNT(*) FROM (SELECT InvoiceID, StockItemID, Quantity, UnitPrice FROM Sales.InvoiceLines"
                            " GROUP BY InvoiceID, StockItemID, Quantity, UnitPrice HAVING COUNT(*) > 1) x")
        inc = db.scalar(cn, "SELECT COUNT(*) FROM Sales.InvoiceLines WHERE ABS(ExtendedPrice - (Quantity*UnitPrice + TaxAmount)) > 0.05")
        q = db.query_records(cn, "SELECT AVG(CAST(Quantity AS float)) media, STDEV(Quantity) sd, MAX(Quantity) maximo FROM Sales.InvoiceLines")[0]
        multi = db.scalar(cn, "SELECT COUNT(*) FROM (SELECT StockItemID FROM Warehouse.StockItemStockGroups GROUP BY StockItemID HAVING COUNT(*) > 1) x")
    parts.append("## Hallazgos del perfilado\n\n"
                 f"- Posibles duplicados de negocio en líneas (misma factura, artículo, cantidad y precio): **{dup}**. "
                 "La clave técnica `InvoiceLineID` es única; estas filas se conservan (pueden ser líneas legítimas repetidas).\n"
                 f"- Líneas con `ExtendedPrice` inconsistente (> 0.05): **{inc}** (la fuente original no tiene ninguna; "
                 "las que aparezcan provienen de la simulación de registros sucios y van a cuarentena por R-IL-04).\n"
                 f"- Cantidad: media {q['media']:.1f}, desviación {q['sd']:.1f}, máximo {q['maximo']} → umbral de outlier media+4σ = {q['media'] + 4*q['sd']:.0f}.\n"
                 f"- Artículos que pertenecen a más de un grupo de stock (relación N:M): **{multi}** → riesgo de multiplicar medidas; "
                 "se asigna una categoría principal (menor StockGroupID).\n"
                 "- `Customers.BuyingGroupID` y `Customers.CreditLimit` tienen nulos con significado de negocio (“No aplica”): se conservan.\n"
                 "- `StockItems.Brand` y `Size` tienen nulos: se estandarizan como 'Sin marca' / 'N/A'.\n")
    (OUT / "01_perfil_fuente.md").write_text("".join(parts), encoding="utf-8")


DICT_SQL = """
SELECT s.name + '.' + t.name AS tabla, c.name AS columna, ty.name +
       CASE WHEN ty.name IN ('nvarchar','varchar','char') THEN '(' + IIF(c.max_length=-1,'max',CAST(c.max_length/IIF(ty.name='nvarchar',2,1) AS varchar)) + ')'
            WHEN ty.name = 'decimal' THEN '(' + CAST(c.precision AS varchar) + ',' + CAST(c.scale AS varchar) + ')' ELSE '' END AS tipo,
       IIF(c.is_nullable=1,'sí','no') AS nulo,
       IIF(EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.indexes i ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                   WHERE i.is_primary_key=1 AND ic.object_id=c.object_id AND ic.column_id=c.column_id),'PK','') +
       ISNULL((SELECT TOP 1 ' FK→' + OBJECT_SCHEMA_NAME(fk.referenced_object_id) + '.' + OBJECT_NAME(fk.referenced_object_id)
               FROM sys.foreign_key_columns fk WHERE fk.parent_object_id=c.object_id AND fk.parent_column_id=c.column_id),'') AS clave
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns c ON c.object_id=t.object_id
JOIN sys.types ty ON ty.user_type_id=c.user_type_id
WHERE {where}
ORDER BY s.name, t.name, c.column_id
"""


def dictionaries() -> None:
    with db.connection(config.DB_SOURCE) as cn:
        names = ",".join(f"'{e.source}'" for e in ENTITIES)
        src = db.query_df(cn, DICT_SQL.format(where=f"s.name + '.' + t.name IN ({names})"))
    used = {e.source: set(e.columns) for e in ENTITIES}
    src["extraída"] = [("sí" if r.columna in used[r.tabla] else "") for r in src.itertuples()]
    out = [header("Diccionario de datos — fuente (tablas usadas)"),
           "Columnas marcadas como *extraída* se copian a staging; el resto (teléfonos, correos, fotos, geografía) se excluye por minimización de datos.\n\n"]
    for t, g in src.groupby("tabla", sort=False):
        out.append(f"## {t}\n\n{md_table(g.drop(columns='tabla'), 80)}\n")
    (OUT / "02_diccionario_fuente.md").write_text("".join(out), encoding="utf-8")

    with db.connection(config.DB_DW) as cn:
        dw = db.query_df(cn, DICT_SQL.format(where="s.name IN ('dw','ops','ml','ai')"))
    out = [header("Diccionario de datos — Data Warehouse WWI_DW")]
    for t, g in dw.groupby("tabla", sort=False):
        out.append(f"## {t}\n\n{md_table(g.drop(columns='tabla'), 80)}\n")
    (OUT / "03_diccionario_dw.md").write_text("".join(out), encoding="utf-8")


def load_results() -> None:
    out = [header("Resultados de carga, reconciliación y calidad")]
    with db.connection(config.DB_DW) as cn:
        out.append("## Ejecuciones ETL\n\n" + md_table(db.query_df(cn,
            "SELECT ExecutionID, Mode, TriggeredBy, StartTime, EndTime, DATEDIFF(SECOND,StartTime,EndTime) seg, Status,"
            " LEFT(ErrorDetail,80) error FROM ops.EtlExecution ORDER BY ExecutionID")) + "\n")
        first = db.scalar(cn, "SELECT MIN(ExecutionID) FROM ops.EtlExecution WHERE Mode='initial' AND Status='success'")
        last_inc = db.scalar(cn, "SELECT MAX(e.ExecutionID) FROM ops.EtlExecution e JOIN ops.EtlStepLog s ON s.ExecutionID=e.ExecutionID"
                                 " WHERE e.Mode='incremental' AND e.Status='success' AND s.StepName='load:dw.FactSales' AND s.RowsInserted>0")
        for label, eid in (("Carga inicial", first), ("Carga incremental con cambios simulados", last_inc)):
            if eid:
                out.append(f"## Pasos — {label} (ejecución {eid})\n\n" + md_table(db.query_df(cn,
                    "SELECT StepName, RowsRead, RowsInserted, RowsUpdated, RowsRejected, WatermarkStart, WatermarkEnd, Status"
                    " FROM ops.EtlStepLog WHERE ExecutionID=? ORDER BY StepLogID", [eid]), 80) + "\n")
        out.append("## Reconciliación (última)\n\n" + md_table(db.query_df(cn,
            "SELECT ExecutionID, Layer, ObjectName, RowCountValue, AmountValue, Notes FROM ops.Reconciliation"
            " WHERE ExecutionID=(SELECT MAX(ExecutionID) FROM ops.Reconciliation) ORDER BY Layer")) + "\n")
        out.append("## Calidad de datos (última ejecución)\n\n" + md_table(db.query_df(cn,
            "SELECT RuleID, QualityDimension, ObjectName, Description, MetricValue, Threshold, Passed FROM ops.DataQualityResult"
            " WHERE ExecutionID=(SELECT MAX(ExecutionID) FROM ops.DataQualityResult) ORDER BY RuleID")) + "\n")
        out.append("## Cuarentena\n\n" + md_table(db.query_df(cn,
            "SELECT RejectedID, ExecutionID, SourceObject, BusinessKey, RuleID, RuleDescription, Status, LEFT(RecordJson,80) registro"
            " FROM WWI_Staging.quarantine.RejectedRecord ORDER BY RejectedID")) + "\n")
        out.append("## SCD Tipo 2 — clientes con historia\n\n" + md_table(db.query_df(cn,
            "SELECT CustomerKey, CustomerID, CustomerName, CustomerCategory, BuyingGroup, ValidFrom, ValidTo, IsCurrent FROM dw.DimCustomer"
            " WHERE CustomerID IN (SELECT CustomerID FROM dw.DimCustomer GROUP BY CustomerID HAVING COUNT(*)>1) ORDER BY CustomerID, ValidFrom")) + "\n")
        out.append("## Imputación documentada (precio derivado)\n\n" + md_table(db.query_df(cn,
            "SELECT InvoiceLineID, Quantity, UnitPrice, ExtendedPrice, TaxAmount, IsUnitPriceDerived, Description FROM WWI_Staging.clean.InvoiceLines"
            " WHERE IsUnitPriceDerived=1")) + "\n")
        out.append("## Conteo de filas en el DW\n\n" + md_table(db.query_df(cn,
            "SELECT 'FactSales' t, COUNT(*) n FROM dw.FactSales UNION ALL SELECT 'DimCustomer', COUNT(*) FROM dw.DimCustomer UNION ALL"
            " SELECT 'DimProduct', COUNT(*) FROM dw.DimProduct UNION ALL SELECT 'DimEmployee', COUNT(*) FROM dw.DimEmployee UNION ALL"
            " SELECT 'DimGeography', COUNT(*) FROM dw.DimGeography UNION ALL SELECT 'DimDate', COUNT(*) FROM dw.DimDate")) + "\n")
        out.append("## Alertas y entregas\n\n" + md_table(db.query_df(cn,
            "SELECT a.AlertID, a.CreatedAt, a.AlertType, a.Severity, a.Entity, a.ObservedValue, a.ThresholdValue, a.PeriodStart, a.Origin,"
            " a.IsSimulated, a.Status, d.Channel, d.Status entrega, d.Attempts, LEFT(d.Detail,60) detalle FROM ops.Alert a"
            " LEFT JOIN ops.NotificationDelivery d ON d.AlertID=a.AlertID ORDER BY a.AlertID, d.Channel")) + "\n")
    (OUT / "04_resultados_carga.md").write_text("".join(out), encoding="utf-8")


def kpi_validation() -> None:
    out = [header("Validación de KPIs y tiempos de respuesta"),
           "Cada KPI del servicio analítico (vista `dw.vw_SalesAnalytics`) se compara con una consulta SQL independiente sobre `dw.FactSales` y dimensiones.\n\n"]
    cases = [("2015 completo", analytics.Filters(pd.Timestamp("2015-01-01").date(), pd.Timestamp("2015-12-31").date())),
             ("2016-Q1 Southeast + Clothing", analytics.Filters(pd.Timestamp("2016-01-01").date(), pd.Timestamp("2016-03-31").date(),
                                                              {"territorio": "Southeast", "categoria": "Clothing"})),
             ("Período sin datos (2030-01)", analytics.Filters(pd.Timestamp("2030-01-01").date(), pd.Timestamp("2030-01-31").date()))]
    rows = []
    with db.connection(config.DB_DW) as cn:
        for name, f in cases:
            t0 = time.perf_counter(); k = analytics.kpis(f)["actual"]; ms = (time.perf_counter() - t0) * 1000
            extra, params = "", [f.start, f.end]
            if "territorio" in f.equals:
                extra = " AND g.SalesTerritory=? AND p.Category=?"; params += [f.equals["territorio"], f.equals["categoria"]]
            e = db.query_records(cn, "SELECT ISNULL(SUM(f.NetAmount),0) net, ISNULL(SUM(f.LineProfit),0) profit, COUNT(DISTINCT f.InvoiceID) inv"
                                     " FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey=f.DateKey JOIN dw.DimGeography g ON g.GeographyKey=f.GeographyKey"
                                     " JOIN dw.DimProduct p ON p.ProductKey=f.ProductKey WHERE d.[Date] BETWEEN ? AND ?" + extra, params)[0]
            rows.append({"caso": name, "ventas API": k["ventas_netas"], "ventas SQL": float(e["net"]), "ganancia API": k["ganancia"],
                         "ganancia SQL": float(e["profit"]), "facturas API": k["facturas"], "facturas SQL": e["inv"],
                         "coincide": abs(k["ventas_netas"] - float(e["net"])) < 0.01 and k["facturas"] == e["inv"], "ms servicio": round(ms)})
    out.append(md_table(pd.DataFrame(rows)) + "\n")
    timings = []
    for name, fn in [("kpis (todo el rango)", lambda: analytics.kpis(analytics.Filters())),
                     ("tendencia mensual", lambda: analytics.trend(analytics.Filters(), "mes")),
                     ("ventas por producto top 10", lambda: analytics.breakdown(analytics.Filters(), "producto", 10)),
                     ("detalle página 1 (25 filas)", lambda: analytics.detail(analytics.Filters(), 1, 25)),
                     ("pronóstico", lambda: analytics.forecasts())]:
        t0 = time.perf_counter(); fn(); timings.append({"consulta": name, "ms": round((time.perf_counter() - t0) * 1000)})
    out.append("## Tiempos de respuesta del servicio analítico (sin caché, SQL Server Express local)\n\n" + md_table(pd.DataFrame(timings)))
    (OUT / "05_validacion_kpis.md").write_text("".join(out), encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    profile_source(); dictionaries(); load_results(); kpi_validation()
    print("Evidencias generadas en", OUT)
