"""Servicio analítico: ÚNICA capa que consulta el Data Warehouse para BI, asistente generativo y alertas.

- Solo lee la vista aprobada dw.vw_SalesAnalytics y tablas ops/ml.
- Dimensiones y granularidades en LISTA BLANCA (los nombres de columna nunca vienen del usuario).
- Todos los valores van como parámetros (?) -> sin inyección SQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from common import config, db

DIMENSIONS = {
    "territorio": "SalesTerritory", "estado": "StateProvince", "ciudad": "City", "categoria": "Category",
    "producto": "ProductName", "marca": "Brand", "cliente": "CustomerName", "categoria_cliente": "CustomerCategory",
    "grupo_compra": "BuyingGroup", "vendedor": "Salesperson", "anio": "Year",
}
GRAINS = {"anio": "CAST([Year] AS varchar(4))", "trimestre": "YearQuarter", "mes": "YearMonth",
          "semana": "CONVERT(char(10), WeekStart, 23)"}
FILTER_COLUMNS = {"territorio": "SalesTerritory", "categoria": "Category", "categoria_cliente": "CustomerCategory",
                  "grupo_compra": "BuyingGroup", "estado": "StateProvince", "cliente": "CustomerName",
                  "producto": "ProductName"}
MIN_DATE, MAX_DATE = date(2000, 1, 1), date(2100, 12, 31)


class ValidationError(ValueError):
    pass


@dataclass
class Filters:
    start: date | None = None
    end: date | None = None
    equals: dict[str, str] = field(default_factory=dict)   # clave de FILTER_COLUMNS -> valor

    def validate(self) -> "Filters":
        for d in (self.start, self.end):
            if d is not None and not (MIN_DATE <= d <= MAX_DATE):
                raise ValidationError("Fecha fuera de rango permitido")
        if self.start and self.end and self.end < self.start:
            raise ValidationError("La fecha final es anterior a la inicial")
        for k, v in self.equals.items():
            if k not in FILTER_COLUMNS:
                raise ValidationError(f"Filtro no permitido: {k}")
            if v is not None and len(str(v)) > 100:
                raise ValidationError("Valor de filtro demasiado largo")
        self.equals = {k: v for k, v in self.equals.items() if v not in (None, "")}
        return self

    def where(self) -> tuple[str, list]:
        sql, params = ["1 = 1"], []
        if self.start:
            sql.append("InvoiceDate >= ?"); params.append(self.start)
        if self.end:
            sql.append("InvoiceDate <= ?"); params.append(self.end)
        for k, v in self.equals.items():
            sql.append(f"{FILTER_COLUMNS[k]} = ?"); params.append(v)
        return " AND ".join(sql), params


def _num(v: Any) -> Any:
    return float(v) if isinstance(v, Decimal) else v


def _clean(rows: list[dict]) -> list[dict]:
    return [{k: (_num(v) if not isinstance(v, (date,)) else v.isoformat()) for k, v in r.items()} for r in rows]


def _q(sql: str, params: list | None = None) -> list[dict]:
    with db.connection(config.DB_DW, role="api") as cn:
        return _clean(db.query_records(cn, sql, params or []))


KPI_SQL = """
SELECT CAST(ISNULL(SUM(NetAmount),0) AS decimal(19,2)) AS ventas_netas,
       CAST(ISNULL(SUM(LineProfit),0) AS decimal(19,2)) AS ganancia,
       CAST(100.0 * SUM(LineProfit) / NULLIF(SUM(NetAmount),0) AS decimal(9,2)) AS margen_pct,
       COUNT(DISTINCT InvoiceID) AS facturas,
       ISNULL(SUM(Quantity),0) AS unidades,
       CAST(SUM(NetAmount) / NULLIF(COUNT(DISTINCT InvoiceID),0) AS decimal(19,2)) AS ticket_promedio,
       COUNT(DISTINCT CustomerID) AS clientes_activos,
       MIN(InvoiceDate) AS primera_fecha, MAX(InvoiceDate) AS ultima_fecha
FROM dw.vw_SalesAnalytics WHERE {where}
"""


def data_range() -> dict:
    r = _q("SELECT MIN(d.[Date]) AS desde, MAX(d.[Date]) AS hasta FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey")
    return r[0]


def kpis(f: Filters) -> dict:
    f.validate()
    rng = data_range()
    start = f.start or date.fromisoformat(rng["desde"])
    end = f.end or date.fromisoformat(rng["hasta"])
    cur_f = Filters(start, end, dict(f.equals))
    days = (end - start).days + 1
    prev_f = Filters(start - timedelta(days=days), start - timedelta(days=1), dict(f.equals))
    w, p = cur_f.where()
    current = _q(KPI_SQL.format(where=w), p)[0]
    w2, p2 = prev_f.where()
    previous = _q(KPI_SQL.format(where=w2), p2)[0]
    delta = {}
    for k in ("ventas_netas", "ganancia", "facturas", "unidades", "ticket_promedio", "clientes_activos"):
        a, b = current.get(k), previous.get(k)
        delta[k] = round((a - b) / b * 100, 2) if a is not None and b else None
    delta["margen_pct"] = (round(current["margen_pct"] - previous["margen_pct"], 2)
                           if current.get("margen_pct") is not None and previous.get("margen_pct") is not None else None)
    return {"periodo": {"desde": start.isoformat(), "hasta": end.isoformat()},
            "periodo_anterior": {"desde": prev_f.start.isoformat(), "hasta": prev_f.end.isoformat()},
            "actual": current, "anterior": previous, "variacion_pct": delta, "filtros": f.equals,
            "fuente": "dw.vw_SalesAnalytics (FactSales, grano línea de factura)"}


def trend(f: Filters, grain: str = "mes") -> list[dict]:
    if grain not in GRAINS:
        raise ValidationError(f"Granularidad no permitida: {grain}")
    w, p = f.validate().where()
    g = GRAINS[grain]
    return _q(f"SELECT {g} AS periodo, CAST(SUM(NetAmount) AS decimal(19,2)) AS ventas_netas,"
              f" CAST(SUM(LineProfit) AS decimal(19,2)) AS ganancia, COUNT(DISTINCT InvoiceID) AS facturas"
              f" FROM dw.vw_SalesAnalytics WHERE {w} GROUP BY {g} ORDER BY periodo", p)


def breakdown(f: Filters, dimension: str, top_n: int = 10) -> list[dict]:
    if dimension not in DIMENSIONS:
        raise ValidationError(f"Dimensión no permitida: {dimension}")
    top_n = max(1, min(int(top_n), 50))
    w, p = f.validate().where()
    col = DIMENSIONS[dimension]
    return _q(f"SELECT TOP (?) CAST({col} AS nvarchar(100)) AS miembro, CAST(SUM(NetAmount) AS decimal(19,2)) AS ventas_netas,"
              f" CAST(SUM(LineProfit) AS decimal(19,2)) AS ganancia, SUM(Quantity) AS unidades,"
              f" COUNT(DISTINCT InvoiceID) AS facturas,"
              f" CAST(100.0 * SUM(NetAmount) / NULLIF(SUM(SUM(NetAmount)) OVER (), 0) AS decimal(9,2)) AS participacion_pct"
              f" FROM dw.vw_SalesAnalytics WHERE {w} GROUP BY {col} ORDER BY SUM(NetAmount) DESC", [top_n, *p])


def compare_periods(dimension: str, cur_start: date, cur_end: date, prev_start: date, prev_end: date,
                    equals: dict | None = None, top_n: int = 10) -> list[dict]:
    if dimension not in DIMENSIONS:
        raise ValidationError(f"Dimensión no permitida: {dimension}")
    Filters(cur_start, cur_end, dict(equals or {})).validate()
    Filters(prev_start, prev_end, dict(equals or {})).validate()
    w, p = Filters(None, None, dict(equals or {})).validate().where()
    col = DIMENSIONS[dimension]
    top_n = max(1, min(int(top_n), 50))
    sql = f"""
    SELECT TOP (?) miembro, actual, anterior,
           CAST(100.0 * (actual - anterior) / NULLIF(anterior, 0) AS decimal(9,2)) AS variacion_pct
    FROM (SELECT CAST({col} AS nvarchar(100)) AS miembro,
                 CAST(SUM(IIF(InvoiceDate BETWEEN ? AND ?, NetAmount, 0)) AS decimal(19,2)) AS actual,
                 CAST(SUM(IIF(InvoiceDate BETWEEN ? AND ?, NetAmount, 0)) AS decimal(19,2)) AS anterior
          FROM dw.vw_SalesAnalytics WHERE {w} AND (InvoiceDate BETWEEN ? AND ? OR InvoiceDate BETWEEN ? AND ?)
          GROUP BY {col}) x
    ORDER BY ABS(actual - anterior) DESC"""
    return _q(sql, [top_n, cur_start, cur_end, prev_start, prev_end, *p, cur_start, cur_end, prev_start, prev_end])


def detail(f: Filters, page: int = 1, page_size: int = 25) -> dict:
    page = max(1, int(page)); page_size = max(1, min(int(page_size), 200))
    w, p = f.validate().where()
    total = _q(f"SELECT COUNT(*) AS n FROM dw.vw_SalesAnalytics WHERE {w}", p)[0]["n"]
    rows = _q(f"SELECT InvoiceID, InvoiceLineID, InvoiceDate, CustomerName, SalesTerritory, City, Category, ProductName,"
              f" Quantity, UnitPrice, NetAmount, LineProfit FROM dw.vw_SalesAnalytics WHERE {w}"
              f" ORDER BY InvoiceDate DESC, InvoiceLineID DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
              [*p, (page - 1) * page_size, page_size])
    return {"total": total, "page": page, "page_size": page_size, "rows": rows}


def filter_options() -> dict:
    out = {}
    for key, col in (("territorio", "SalesTerritory"), ("categoria", "Category"), ("categoria_cliente", "CustomerCategory"),
                     ("grupo_compra", "BuyingGroup")):
        out[key] = [r["v"] for r in _q(f"SELECT DISTINCT {col} AS v FROM dw.vw_SalesAnalytics ORDER BY v")]
    out["rango_fechas"] = data_range()
    return out


def freshness() -> dict:
    last = _q("SELECT TOP 1 ExecutionID, Mode, EndTime FROM ops.EtlExecution WHERE Status = 'success' ORDER BY EndTime DESC")
    return {"ultima_carga_exitosa": last[0] if last else None, "datos": data_range()}


def forecasts(territory: str | None = None) -> dict:
    model = _q("SELECT TOP 1 ModelVersion, Algorithm, TrainedAt, MetricsJson FROM ml.ModelRegistry WHERE IsActive = 1")
    if not model:
        return {"modelo": None, "predicciones": []}
    m = model[0]
    sql = ("SELECT p.SalesTerritory, p.AsOfWeek, p.TargetWeekStart, p.HorizonWeeks, p.PredictedNetAmount, p.PredictionDate"
           " FROM ml.Prediction p WHERE p.ModelVersion = ?"
           " AND p.AsOfWeek = (SELECT MAX(AsOfWeek) FROM ml.Prediction WHERE ModelVersion = ?)")
    params: list = [m["ModelVersion"], m["ModelVersion"]]
    if territory:
        sql += " AND p.SalesTerritory = ?"; params.append(territory)
    preds = _q(sql + " ORDER BY p.SalesTerritory, p.HorizonWeeks", params)
    return {"modelo": {"version": m["ModelVersion"], "algoritmo": m["Algorithm"], "entrenado": str(m["TrainedAt"])},
            "predicciones": preds, "tipo": "PREDICCIÓN (no es dato histórico)"}


def recent_alerts(limit: int = 20, status: str | None = None) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    sql = ("SELECT TOP (?) AlertID, CreatedAt, AlertType, Severity, Indicator, Entity, ObservedValue, ThresholdValue,"
           " ReferenceValue, PeriodStart, PeriodEnd, Origin, ModelVersion, Message, Explanation, ExplanationIsAIGenerated,"
           " RecommendedAction, Status, IsSimulated FROM ops.Alert")
    params: list = [limit]
    if status:
        sql += " WHERE Status = ?"; params.append(status)
    rows = _q(sql + " ORDER BY AlertID DESC", params)
    for r in rows:
        r["CreatedAt"] = str(r["CreatedAt"])
    return rows
