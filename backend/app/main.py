"""API de la plataforma (FastAPI). El navegador NUNCA se conecta a SQL Server: todo pasa por esta capa.

Ejecutar:  uvicorn backend.app.main:app --port 8000      (documentación interactiva en /docs)
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from backend.app import security
from common import analytics, config, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

app = FastAPI(title="Plataforma de Datos WWI - API", version="1.0.0",
              description="BI, Machine Learning, IA generativa, alertas y monitoreo sobre el Data Warehouse WWI_DW.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
assistant_limiter = security.RateLimiter(config.ASSISTANT_RATE_PER_MINUTE)


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Response-Time-ms"] = f"{ms:.0f}"
    if request.url.path.startswith("/api/"):
        log.info("%s %s -> %s %.0f ms", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(analytics.ValidationError)
async def validation_handler(_: Request, exc: analytics.ValidationError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ------------------------------------------------------------------ helpers
def filters(start: date | None = None, end: date | None = None, territorio: str | None = None, categoria: str | None = None,
            categoria_cliente: str | None = None, grupo_compra: str | None = None, estado: str | None = None,
            cliente: str | None = None, producto: str | None = None) -> analytics.Filters:
    eq = {"territorio": territorio, "categoria": categoria, "categoria_cliente": categoria_cliente,
          "grupo_compra": grupo_compra, "estado": estado, "cliente": cliente, "producto": producto}
    return analytics.Filters(start, end, eq).validate()


def _ops(sql: str, params: list | None = None) -> list[dict]:
    with db.connection(config.DB_DW, role="api") as cn:
        rows = db.query_records(cn, sql, params or [])
    return analytics._clean(rows)


# ------------------------------------------------------------------ auth
@app.post("/api/auth/login", tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = security.authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    return {"access_token": security.create_token(user), "token_type": "bearer", "user": user}


@app.get("/api/auth/me", tags=["auth"])
def me(user: dict = Depends(security.current_user)):
    return user


@app.get("/api/health", tags=["ops"])
def health():
    try:
        with db.connection(config.DB_DW, role="api") as cn:
            db.scalar(cn, "SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "database": str(exc)[:200]}


# ------------------------------------------------------------------ BI
@app.get("/api/meta/filters", tags=["bi"])
def meta_filters(_: dict = Depends(security.current_user)):
    return analytics.filter_options()


@app.get("/api/meta/freshness", tags=["bi"])
def meta_freshness(_: dict = Depends(security.current_user)):
    return analytics.freshness()


@app.get("/api/kpis", tags=["bi"])
def get_kpis(f: analytics.Filters = Depends(filters), _: dict = Depends(security.current_user)):
    return analytics.kpis(f)


@app.get("/api/sales/trend", tags=["bi"])
def get_trend(grain: Literal["anio", "trimestre", "mes", "semana"] = "mes", f: analytics.Filters = Depends(filters),
              _: dict = Depends(security.current_user)):
    return analytics.trend(f, grain)


@app.get("/api/sales/by", tags=["bi"])
def get_breakdown(dimension: str = Query("territorio"), top_n: int = Query(10, ge=1, le=50),
                  f: analytics.Filters = Depends(filters), _: dict = Depends(security.current_user)):
    return analytics.breakdown(f, dimension, top_n)


@app.get("/api/sales/compare", tags=["bi"])
def get_compare(dimension: str, actual_inicio: date, actual_fin: date, anterior_inicio: date, anterior_fin: date,
                top_n: int = Query(10, ge=1, le=50), _: dict = Depends(security.current_user)):
    return analytics.compare_periods(dimension, actual_inicio, actual_fin, anterior_inicio, anterior_fin, {}, top_n)


@app.get("/api/sales/detail", tags=["bi"])
def get_detail(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
               f: analytics.Filters = Depends(filters), _: dict = Depends(security.current_user)):
    return analytics.detail(f, page, page_size)


# ------------------------------------------------------------------ ML
@app.get("/api/ml/forecast", tags=["ml"])
def ml_forecast(territorio: str | None = None, _: dict = Depends(security.current_user)):
    return analytics.forecasts(territorio)


@app.get("/api/ml/models", tags=["ml"])
def ml_models(_: dict = Depends(security.current_user)):
    rows = _ops("SELECT ModelVersion, ModelName, Algorithm, TrainedAt, TrainStart, TrainEnd, ValidStart, ValidEnd, TestStart,"
                " TestEnd, MetricsJson, IsActive FROM ml.ModelRegistry ORDER BY TrainedAt DESC")
    for r in rows:
        r["metrics"] = json.loads(r.pop("MetricsJson"))
    return rows


@app.get("/api/ml/backtest", tags=["ml"])
def ml_backtest(territorio: str = "Southeast", _: dict = Depends(security.current_user)):
    return _ops("SELECT b.WeekStart, b.ActualNetAmount, b.PredictedNetAmount, b.BaselineNetAmount FROM ml.BacktestResult b"
                " JOIN ml.ModelRegistry m ON m.ModelVersion = b.ModelVersion AND m.IsActive = 1"
                " WHERE b.SalesTerritory = ? ORDER BY b.WeekStart", [territorio])


@app.post("/api/ml/predict", tags=["ml"])
def ml_predict(_: dict = Depends(security.require_admin)):
    from machine_learning.predict import run_batch_prediction
    out = run_batch_prediction()
    return {"filas": len(out), "modelo": out.ModelVersion.iloc[0], "origen": str(out.AsOfWeek.iloc[0])}


# ------------------------------------------------------------------ GenAI
class Question(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=config.ASSISTANT_MAX_QUESTION_CHARS)


@app.post("/api/assistant/ask", tags=["genai"])
def assistant_ask(q: Question, user: dict = Depends(security.current_user)):
    from generative_ai import assistant
    import anthropic
    assistant_limiter.check(user["username"])
    try:
        return assistant.ask(q.pregunta, user["username"])
    except (assistant.AssistantNotConfigured, assistant.AssistantUnavailable) as exc:
        # Proveedor no configurado o no disponible: se informa el problema; nunca se simula una respuesta.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "El proveedor de IA limitó la tasa; reintente") from exc
    except anthropic.APIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error del proveedor de IA") from exc


@app.get("/api/assistant/status", tags=["genai"])
def assistant_status(_: dict = Depends(security.current_user)):
    from generative_ai import assistant
    return assistant.status()


# ------------------------------------------------------------------ Alertas
class AlertStatus(BaseModel):
    status: Literal["nueva", "atendida", "descartada", "resuelta"]


@app.get("/api/alerts", tags=["alertas"])
def list_alerts(limit: int = Query(50, ge=1, le=200), estado: str | None = None,
                _: dict = Depends(security.current_user)):
    return analytics.recent_alerts(limit, estado)


@app.patch("/api/alerts/{alert_id}", tags=["alertas"])
def update_alert(alert_id: int, body: AlertStatus, _: dict = Depends(security.current_user)):
    with db.connection(config.DB_DW, role="api") as cn:
        cur = cn.cursor()
        cur.execute("UPDATE ops.Alert SET Status = ?, UpdatedAt = SYSDATETIME() WHERE AlertID = ?", body.status, alert_id)
        if cur.rowcount == 0:
            raise HTTPException(404, "Alerta no encontrada")
    return {"AlertID": alert_id, "Status": body.status}


@app.get("/api/alerts/{alert_id}/deliveries", tags=["alertas"])
def alert_deliveries(alert_id: int, _: dict = Depends(security.current_user)):
    return _ops("SELECT Channel, Recipient, Status, Attempts, LastError, Detail, CreatedAt, DeliveredAt"
                " FROM ops.NotificationDelivery WHERE AlertID = ?", [alert_id])


@app.post("/api/alerts/evaluate", tags=["alertas"])
def alerts_evaluate(_: dict = Depends(security.require_admin)):
    from notifications import alerts
    return alerts.evaluate_and_notify(trigger="api")


@app.post("/api/alerts/test", tags=["alertas"])
def alerts_test(_: dict = Depends(security.require_admin)):
    from notifications import alerts
    return {"AlertID": alerts.fire_test_alert(), "simulada": True}


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket, token: str):
    """Envía alertas nuevas en cuanto aparecen en ops.Alert (consulta cada 5 s del lado servidor)."""
    try:
        security.decode_token(token)
    except HTTPException:
        await ws.close(code=4401)
        return
    await ws.accept()
    last_id = (await asyncio.to_thread(_ops, "SELECT ISNULL(MAX(AlertID), 0) AS m FROM ops.Alert"))[0]["m"]
    try:
        while True:
            rows = await asyncio.to_thread(_ops, "SELECT AlertID, CreatedAt, AlertType, Severity, Entity, Message, IsSimulated"
                                                  " FROM ops.Alert WHERE AlertID > ? ORDER BY AlertID", [last_id])
            for r in rows:
                await ws.send_json({"tipo": "alerta_nueva", **r})
                last_id = r["AlertID"]
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


# ------------------------------------------------------------------ Operación / monitoreo
@app.get("/api/ops/summary", tags=["ops"])
def ops_summary(_: dict = Depends(security.current_user)):
    runs = _ops("SELECT TOP 15 e.ExecutionID, e.Mode, e.TriggeredBy, e.StartTime, e.EndTime, e.Status,"
                " DATEDIFF(SECOND, e.StartTime, e.EndTime) AS DurationSec, LEFT(e.ErrorDetail, 300) AS ErrorDetail,"
                " (SELECT SUM(RowsRead) FROM ops.EtlStepLog s WHERE s.ExecutionID = e.ExecutionID AND s.StepName LIKE 'extract:%') AS RowsExtracted,"
                " (SELECT SUM(RowsRejected) FROM ops.EtlStepLog s WHERE s.ExecutionID = e.ExecutionID AND s.StepName LIKE 'clean:%') AS RowsRejected,"
                " (SELECT SUM(RowsInserted) FROM ops.EtlStepLog s WHERE s.ExecutionID = e.ExecutionID AND s.StepName = 'load:dw.FactSales') AS FactsInserted"
                " FROM ops.EtlExecution e ORDER BY e.ExecutionID DESC")
    last_ok = next((r for r in runs if r["Status"] == "success"), None)
    quality = _ops("SELECT RuleID, QualityDimension, ObjectName, Description, MetricValue, Threshold, Passed FROM ops.DataQualityResult"
                   " WHERE ExecutionID = (SELECT MAX(ExecutionID) FROM ops.DataQualityResult) ORDER BY RuleID")
    recon = _ops("SELECT Layer, ObjectName, RowCountValue, AmountValue, Notes FROM ops.Reconciliation"
                 " WHERE ExecutionID = (SELECT MAX(ExecutionID) FROM ops.Reconciliation) ORDER BY Layer")
    model = _ops("SELECT TOP 1 ModelVersion, Algorithm, TrainedAt FROM ml.ModelRegistry WHERE IsActive = 1")
    notif = _ops("SELECT Channel, Status, COUNT(*) AS n FROM ops.NotificationDelivery GROUP BY Channel, Status")
    quarantine = _ops("SELECT TOP 20 RejectedID, ExecutionID, SourceObject, BusinessKey, RuleID, RuleDescription, Status, RejectedAt"
                      " FROM WWI_Staging.quarantine.RejectedRecord ORDER BY RejectedID DESC")
    watermarks = _ops("SELECT SourceObject, WatermarkColumn, WatermarkValue, UpdatedAt FROM ops.Watermark ORDER BY SourceObject")
    ai = _ops("SELECT COUNT(*) AS consultas, SUM(IIF(Status = 'ok', 1, 0)) AS exitosas, AVG(LatencyMs) AS latencia_prom_ms"
              " FROM ai.AssistantLog")
    return {"ejecuciones": runs, "ultima_exitosa": last_ok, "calidad": quality, "reconciliacion": recon,
            "modelo_activo": model[0] if model else None, "notificaciones": notif, "cuarentena": quarantine,
            "watermarks": watermarks, "asistente": ai[0] if ai else None}


@app.get("/api/ops/runs/{execution_id}", tags=["ops"])
def ops_run_steps(execution_id: int, _: dict = Depends(security.current_user)):
    return _ops("SELECT StepName, SourceObject, TargetObject, RowsRead, RowsInserted, RowsUpdated, RowsRejected, WatermarkStart,"
                " WatermarkEnd, StartTime, EndTime, Status, LEFT(ErrorDetail, 500) AS ErrorDetail FROM ops.EtlStepLog"
                " WHERE ExecutionID = ? ORDER BY StepLogID", [execution_id])


@app.post("/api/ops/run-pipeline", tags=["ops"])
def run_pipeline(_: dict = Depends(security.require_admin)):
    """Lanza el pipeline en segundo plano (proceso aparte); el estado se ve en /api/ops/summary."""
    subprocess.Popen([sys.executable, "-m", "etl.pipeline", "--triggered-by", "api"], cwd=str(config.ROOT),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"lanzado": True, "detalle": "Pipeline en ejecución; consulte /api/ops/summary"}
