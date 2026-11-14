"""Motor de alertas y notificaciones.

Disparadores:
  R-ALR-01 (regla de negocio): ventas netas de la última semana completa de un territorio caen más de
           ALERT_DROP_THRESHOLD (15 %) frente al promedio de las 4 semanas previas.
  R-ALR-02 (Machine Learning): la predicción h=1 del modelo activo queda por debajo de
           ALERT_ML_THRESHOLD (80 %) del promedio real de las últimas 13 semanas.
  IA generativa: las alertas de severidad 'alta' reciben una explicación + acción recomendada generada por Claude,
           marcada como generada por IA (ExplanationIsAIGenerated = 1).
Control de duplicados: DedupKey único (regla|entidad|período). Re-evaluar no duplica alertas.
Canales: web (ops.Alert + WebSocket del backend) y correo (SMTP si está configurado; si no, archivo .eml en
notifications/outbox marcado como entrega SIMULADA). Reintentos: 3 con backoff.

Uso:  python -m notifications.alerts            # evalúa reglas y notifica
      python -m notifications.alerts --test     # dispara una alerta de PRUEBA (simulada)
"""
from __future__ import annotations

import argparse
import logging
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage

import pandas as pd

from common import config, db

log = logging.getLogger("alerts")
ORIGINAL_DATA_END = pd.Timestamp("2016-05-31")   # después de esta fecha los datos de la fuente son SIMULADOS


# ----------------------------------------------------------------- reglas (puras)
def severity_for_drop(drop: float) -> str:
    return "alta" if drop >= 0.30 else "media" if drop >= 0.20 else "baja"


def evaluate_drop_rule(weekly: pd.DataFrame, last_week: pd.Timestamp, threshold: float) -> list[dict]:
    """weekly: columnas SalesTerritory, WeekStart, NetAmount. Devuelve alertas para caídas > threshold."""
    alerts = []
    for terr, g in weekly.groupby("SalesTerritory"):
        g = g.set_index("WeekStart")["NetAmount"].sort_index()
        if last_week not in g.index:
            continue
        prev = g[g.index < last_week].tail(4)
        if len(prev) < 4 or prev.mean() <= 0:
            continue
        observed, reference = float(g[last_week]), float(prev.mean())
        drop = round(1 - observed / reference, 6)   # redondeo: evita que 15.0000000002 % dispare con umbral 15 %
        if drop > threshold:
            end = last_week + pd.Timedelta(days=6)
            alerts.append({
                "AlertType": "regla", "Severity": severity_for_drop(drop), "Indicator": "Ventas netas semanales",
                "Entity": f"Territorio {terr}", "ObservedValue": round(observed, 2),
                "ThresholdValue": round(reference * (1 - threshold), 2), "ReferenceValue": round(reference, 2),
                "PeriodStart": last_week.date(), "PeriodEnd": end.date(), "Origin": "Regla R-ALR-01", "ModelVersion": None,
                "Message": (f"Las ventas netas de {terr} en la semana {last_week:%Y-%m-%d} fueron {observed:,.2f}, "
                            f"{drop:.1%} por debajo del promedio de las 4 semanas previas ({reference:,.2f}); "
                            f"umbral de caída {threshold:.0%}."),
                "RecommendedAction": "Revisar pedidos y clientes principales del territorio en la semana indicada.",
                "IsSimulated": int(end > ORIGINAL_DATA_END),
                "DedupKey": f"R-ALR-01|{terr}|{last_week:%Y-%m-%d}"})
    return alerts


def evaluate_ml_rule(preds: pd.DataFrame, weekly: pd.DataFrame, ratio: float) -> list[dict]:
    """preds: SalesTerritory, TargetWeekStart, HorizonWeeks, PredictedNetAmount, ModelVersion, AsOfWeek."""
    alerts = []
    for r in preds[preds["HorizonWeeks"] == 1].itertuples():
        hist = weekly[(weekly.SalesTerritory == r.SalesTerritory) & (weekly.WeekStart <= pd.Timestamp(r.AsOfWeek))].tail(13)
        if len(hist) < 13:
            continue
        ref = float(hist.NetAmount.mean())
        pred = float(r.PredictedNetAmount)
        if ref > 0 and pred < ratio * ref:
            tw = pd.Timestamp(r.TargetWeekStart)
            alerts.append({
                "AlertType": "ml", "Severity": "media" if pred >= 0.6 * ref else "alta",
                "Indicator": "Predicción de ventas netas semanales", "Entity": f"Territorio {r.SalesTerritory}",
                "ObservedValue": round(pred, 2), "ThresholdValue": round(ratio * ref, 2), "ReferenceValue": round(ref, 2),
                "PeriodStart": tw.date(), "PeriodEnd": (tw + pd.Timedelta(days=6)).date(),
                "Origin": f"Modelo {r.ModelVersion} (R-ALR-02)", "ModelVersion": r.ModelVersion,
                "Message": (f"[PREDICCIÓN] El modelo {r.ModelVersion} pronostica {pred:,.2f} para {r.SalesTerritory} en la semana "
                            f"{tw:%Y-%m-%d} (horizonte 1), bajo el {ratio:.0%} del promedio de 13 semanas ({ref:,.2f})."),
                "RecommendedAction": "Planificar acciones comerciales preventivas y validar el inventario del territorio.",
                "IsSimulated": int(tw > ORIGINAL_DATA_END),
                "DedupKey": f"R-ALR-02|{r.SalesTerritory}|{tw:%Y-%m-%d}|{r.ModelVersion}"})
    return alerts


# ----------------------------------------------------------------- persistencia
INSERT_SQL = """
SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM ops.Alert WHERE DedupKey = ?)
BEGIN
    INSERT ops.Alert (AlertType, Severity, Indicator, Entity, ObservedValue, ThresholdValue, ReferenceValue, PeriodStart,
                      PeriodEnd, Origin, ModelVersion, Message, RecommendedAction, IsSimulated, DedupKey)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
    SELECT CAST(SCOPE_IDENTITY() AS int) AS id;
END
ELSE SELECT CAST(NULL AS int) AS id;
"""


def save_alert(cn, a: dict) -> int | None:
    cur = cn.cursor()
    cur.execute(INSERT_SQL, a["DedupKey"], a["AlertType"], a["Severity"], a["Indicator"], a["Entity"], a["ObservedValue"],
                a["ThresholdValue"], a["ReferenceValue"], a["PeriodStart"], a["PeriodEnd"], a["Origin"], a["ModelVersion"],
                a["Message"], a["RecommendedAction"], a["IsSimulated"], a["DedupKey"])
    row = db.last_result(cur)
    return row["id"] if row else None


# ----------------------------------------------------------------- entrega
def _send_email(alert: dict) -> str:
    msg = EmailMessage()
    msg["Subject"] = f"[{alert['Severity'].upper()}] {alert['Indicator']} - {alert['Entity']}"
    msg["From"], msg["To"] = config.SMTP_FROM, config.ALERT_EMAIL_TO
    body = [alert["Message"], "", f"Origen: {alert['Origin']}", f"Período: {alert['PeriodStart']} a {alert['PeriodEnd']}",
            f"Acción recomendada: {alert.get('RecommendedAction') or '-'}"]
    if alert.get("Explanation"):
        body += ["", "Explicación (GENERADA POR IA, verificar):", alert["Explanation"]]
    if alert.get("IsSimulated"):
        body += ["", "NOTA: alerta basada en datos SIMULADOS para demostración."]
    msg.set_content("\n".join(body))
    if config.SMTP_HOST:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
            s.send_message(msg)
        return f"SMTP {config.SMTP_HOST}"
    config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTBOX_DIR / f"alerta_{alert['AlertID']}_{datetime.now():%Y%m%d%H%M%S}.eml"
    path.write_bytes(bytes(msg))
    return f"SIMULADO (sin SMTP): {path.relative_to(config.ROOT)}"


def deliver(cn, alert: dict, max_attempts: int = 3) -> None:
    cur = cn.cursor()
    # Canal web: la alerta queda visible en el dashboard y se emite por WebSocket
    cur.execute("IF NOT EXISTS (SELECT 1 FROM ops.NotificationDelivery WHERE AlertID = ? AND Channel = 'web')"
                " INSERT ops.NotificationDelivery (AlertID, Channel, Recipient, Status, Attempts, Detail, DeliveredAt)"
                " VALUES (?, 'web', 'dashboard', 'entregado', 1, 'Publicada en ops.Alert / WebSocket', SYSDATETIME())",
                alert["AlertID"], alert["AlertID"])
    cur.execute("IF NOT EXISTS (SELECT 1 FROM ops.NotificationDelivery WHERE AlertID = ? AND Channel = 'email')"
                " INSERT ops.NotificationDelivery (AlertID, Channel, Recipient, Status) VALUES (?, 'email', ?, 'pendiente')",
                alert["AlertID"], alert["AlertID"], config.ALERT_EMAIL_TO)
    state = db.query_records(cn, "SELECT Status, Attempts FROM ops.NotificationDelivery WHERE AlertID = ? AND Channel = 'email'",
                             [alert["AlertID"]])[0]
    if state["Status"] == "entregado":
        return
    attempts = state["Attempts"]
    for _ in range(max_attempts):
        attempts += 1
        try:
            detail = _send_email(alert)
            cur.execute("UPDATE ops.NotificationDelivery SET Status='entregado', Attempts=?, Detail=?, DeliveredAt=SYSDATETIME(),"
                        " LastError=NULL WHERE AlertID=? AND Channel='email'", attempts, detail, alert["AlertID"])
            log.info("Alerta %s entregada por correo: %s", alert["AlertID"], detail)
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("Fallo de envío alerta %s intento %s: %s", alert["AlertID"], attempts, exc)
            cur.execute("UPDATE ops.NotificationDelivery SET Status='fallido', Attempts=?, LastError=? WHERE AlertID=? AND Channel='email'",
                        attempts, str(exc)[:1000], alert["AlertID"])
            time.sleep(min(2 ** attempts, 8))


def retry_failed_deliveries() -> int:
    """Reintenta entregas pendientes/fallidas y entrega alertas que nunca tuvieron registro de entrega."""
    with db.connection(config.DB_DW) as cn:
        pending = db.query_records(cn, "SELECT a.* FROM ops.Alert a LEFT JOIN ops.NotificationDelivery d"
                                       " ON d.AlertID = a.AlertID AND d.Channel = 'email'"
                                       " WHERE d.DeliveryID IS NULL OR d.Status IN ('pendiente','fallido')")
        for a in pending:
            deliver(cn, a)
    return len(pending)


# ----------------------------------------------------------------- orquestación
def _attach_ai_explanation(cn, alert_id: int) -> None:
    """La IA es opcional: si falla o no está configurada, la alerta se entrega igual sin explicación generada."""
    try:
        from generative_ai.assistant import explain_alert
        a = db.query_records(cn, "SELECT * FROM ops.Alert WHERE AlertID = ?", [alert_id])[0]
        text = explain_alert(a)
    except Exception as exc:  # noqa: BLE001
        log.warning("Explicación IA no disponible para alerta %s: %s", alert_id, exc)
        return
    if text:
        cn.cursor().execute("UPDATE ops.Alert SET Explanation = ?, ExplanationIsAIGenerated = 1, UpdatedAt = SYSDATETIME()"
                            " WHERE AlertID = ?", text, alert_id)


def evaluate_and_notify(trigger: str = "manual", use_ai: bool = True) -> dict:
    from machine_learning.features import load_weekly
    weekly, last_week = load_weekly()
    candidates = evaluate_drop_rule(weekly, last_week, config.ALERT_DROP_THRESHOLD)
    with db.connection(config.DB_DW) as cn:
        preds = db.query_df(cn, "SELECT p.SalesTerritory, p.TargetWeekStart, p.HorizonWeeks, p.PredictedNetAmount, p.ModelVersion,"
                                " p.AsOfWeek FROM ml.Prediction p JOIN ml.ModelRegistry m ON m.ModelVersion = p.ModelVersion"
                                " AND m.IsActive = 1 WHERE p.AsOfWeek = (SELECT MAX(AsOfWeek) FROM ml.Prediction"
                                " WHERE ModelVersion = m.ModelVersion)")
        if not preds.empty:
            candidates += evaluate_ml_rule(preds, weekly, config.ALERT_ML_THRESHOLD)
        created, duplicates = [], 0
        for a in candidates:
            new_id = save_alert(cn, a)
            if new_id is None:
                duplicates += 1
                continue
            created.append(new_id)
            if use_ai and a["Severity"] == "alta":
                _attach_ai_explanation(cn, new_id)
            deliver(cn, db.query_records(cn, "SELECT * FROM ops.Alert WHERE AlertID = ?", [new_id])[0])
    retried = retry_failed_deliveries()
    log.info("Entregas pendientes reintentadas: %s", retried)
    log.info("Alertas (%s): evaluadas=%s nuevas=%s duplicadas_omitidas=%s semana=%s", trigger, len(candidates), len(created),
             duplicates, last_week.date())
    return {"semana_evaluada": str(last_week.date()), "candidatas": len(candidates), "nuevas": created,
            "duplicadas_omitidas": duplicates}


def fire_test_alert(use_ai: bool = True) -> int:
    """Alerta de PRUEBA para la demo (IsSimulated = 1). Cada invocación crea una nueva (DedupKey con timestamp)."""
    now = datetime.now()
    a = {"AlertType": "regla", "Severity": "alta", "Indicator": "Ventas netas semanales (PRUEBA)",
         "Entity": "Territorio Southeast", "ObservedValue": 100000.0, "ThresholdValue": 170000.0, "ReferenceValue": 200000.0,
         "PeriodStart": now.date(), "PeriodEnd": now.date(), "Origin": "Regla R-ALR-01 (evento SIMULADO)", "ModelVersion": None,
         "Message": "[SIMULACIÓN] Caída de 50% de ventas netas frente al promedio de 4 semanas (umbral 15%).",
         "RecommendedAction": "Verificar el flujo de notificación de extremo a extremo.", "IsSimulated": 1,
         "DedupKey": f"TEST|{now:%Y%m%d%H%M%S%f}"}
    with db.connection(config.DB_DW) as cn:
        aid = save_alert(cn, a)
        if use_ai:
            _attach_ai_explanation(cn, aid)
        deliver(cn, db.query_records(cn, "SELECT * FROM ops.Alert WHERE AlertID = ?", [aid])[0])
    return aid


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true", help="Disparar alerta de prueba simulada")
    p.add_argument("--no-ai", action="store_true")
    p.add_argument("--retry", action="store_true", help="Reintentar entregas fallidas")
    a = p.parse_args()
    if a.retry:
        print("Reintentadas:", retry_failed_deliveries())
    elif a.test:
        print("ALERTA_PRUEBA_ID =", fire_test_alert(not a.no_ai))
    else:
        print(evaluate_and_notify(use_ai=not a.no_ai))
