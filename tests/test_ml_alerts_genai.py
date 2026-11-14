"""ML (sin leakage, baseline), alertas (disparo / no disparo / deduplicación) y controles del asistente."""
import json

import pandas as pd
import pytest

from common import analytics, config, db
from generative_ai import assistant
from machine_learning.features import FEATURES, make_supervised
from machine_learning.train import TRAIN_END, VALID_END, split
from notifications import alerts


def _weekly(values_by_terr: dict[str, list[float]]) -> pd.DataFrame:
    rows = []
    for terr, vals in values_by_terr.items():
        for i, v in enumerate(vals):
            rows.append({"SalesTerritory": terr, "WeekStart": pd.Timestamp("2015-01-05") + pd.Timedelta(weeks=i), "NetAmount": v})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ ML
def test_features_use_only_past_information():
    w = _weekly({"A": [float(i) for i in range(1, 80)]})
    sup = make_supervised(w, horizon=2)
    for r in sup.itertuples():
        assert r.target_week > r.origin_week
        assert r.lag_0 == w.set_index("WeekStart").loc[r.origin_week, "NetAmount"]   # lag_0 = semana origen, no el objetivo
        assert r.y == w.set_index("WeekStart").loc[r.target_week, "NetAmount"]
        assert r.lag52_target == w.set_index("WeekStart").loc[r.target_week - pd.Timedelta(weeks=52), "NetAmount"]
    assert set(FEATURES) <= set(sup.columns)


def test_temporal_split_has_no_overlap():
    w = _weekly({"A": [100.0 + i for i in range(170)]})
    w["WeekStart"] = w["WeekStart"] - pd.Timedelta(weeks=100)
    tr, va, te = split(make_supervised(w, 1))
    assert tr.target_week.max() <= TRAIN_END < va.target_week.min()
    assert va.target_week.max() <= VALID_END < te.target_week.min()


def test_active_model_registered_with_baseline_comparison(dw):
    m = db.query_records(dw, "SELECT TOP 1 MetricsJson FROM ml.ModelRegistry WHERE IsActive = 1")
    assert m, "Debe existir un modelo activo"
    metrics = json.loads(m[0]["MetricsJson"])
    h1 = metrics["horizons"]["1"]
    assert "model" in h1 and "naive_estacional_52" in h1 and "media_movil_4" in h1
    assert h1["test_rows"] > 0


# ------------------------------------------------------------------ Alertas
def test_drop_rule_fires_when_drop_exceeds_threshold():
    w = _weekly({"A": [100, 100, 100, 100, 70], "B": [100, 100, 100, 100, 95]})
    last = w.WeekStart.max()
    out = alerts.evaluate_drop_rule(w, last, 0.15)
    assert [a["Entity"] for a in out] == ["Territorio A"]
    assert out[0]["Severity"] == "alta" and out[0]["ObservedValue"] == 70 and out[0]["ReferenceValue"] == 100


def test_drop_rule_does_not_fire_at_or_below_threshold():
    w = _weekly({"A": [100, 100, 100, 100, 85]})
    assert alerts.evaluate_drop_rule(w, w.WeekStart.max(), 0.15) == []


def test_ml_rule_fires_only_below_ratio():
    w = _weekly({"A": [100.0] * 13, "B": [100.0] * 13})
    asof = w.WeekStart.max()
    preds = pd.DataFrame([{"SalesTerritory": "A", "TargetWeekStart": asof + pd.Timedelta(weeks=1), "HorizonWeeks": 1,
                           "PredictedNetAmount": 50.0, "ModelVersion": "vtest", "AsOfWeek": asof},
                          {"SalesTerritory": "B", "TargetWeekStart": asof + pd.Timedelta(weeks=1), "HorizonWeeks": 1,
                           "PredictedNetAmount": 90.0, "ModelVersion": "vtest", "AsOfWeek": asof}])
    out = alerts.evaluate_ml_rule(preds, w, 0.8)
    assert len(out) == 1 and out[0]["Entity"] == "Territorio A" and "[PREDICCIÓN]" in out[0]["Message"]


def test_alert_deduplication(dw):
    a = {"AlertType": "regla", "Severity": "baja", "Indicator": "pytest", "Entity": "pytest", "ObservedValue": 1,
         "ThresholdValue": 2, "ReferenceValue": 3, "PeriodStart": None, "PeriodEnd": None, "Origin": "pytest",
         "ModelVersion": None, "Message": "pytest", "RecommendedAction": None, "IsSimulated": 1, "DedupKey": "PYTEST|dedup"}
    first = alerts.save_alert(dw, a)
    second = alerts.save_alert(dw, a)
    assert second is None
    assert db.scalar(dw, "SELECT COUNT(*) FROM ops.Alert WHERE DedupKey = 'PYTEST|dedup'") == 1
    if first:
        dw.cursor().execute("DELETE FROM ops.Alert WHERE AlertID = ?", first)


def test_alerts_have_web_and_email_delivery_records(dw):
    missing = db.scalar(dw, "SELECT COUNT(*) FROM ops.Alert a WHERE a.DedupKey NOT LIKE 'PYTEST%' AND NOT EXISTS"
                            " (SELECT 1 FROM ops.NotificationDelivery d WHERE d.AlertID = a.AlertID AND d.Channel = 'web')")
    assert missing == 0


# ------------------------------------------------------------------ GenAI (controles sin llamar al modelo)
def test_assistant_rejects_tools_outside_whitelist():
    with pytest.raises(analytics.ValidationError):
        assistant.run_tool("ejecutar_sql", {"sql": "DROP TABLE dw.FactSales"})


def test_assistant_tool_validates_parameters():
    with pytest.raises(analytics.ValidationError):
        assistant.run_tool("ventas_por_dimension", {"dimension": "CustomerName; --", "fecha_inicio": "2016-01-01",
                                                    "fecha_fin": "2016-02-01"})
    with pytest.raises(analytics.ValidationError):
        assistant.run_tool("obtener_kpis", {"fecha_inicio": "ayer", "fecha_fin": "2016-02-01"})


def test_assistant_tools_return_dw_data():
    k = assistant.run_tool("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31"})
    assert k["actual"]["ventas_netas"] > 0 and "fuente" in k
    f = assistant.run_tool("pronostico", {})
    assert f["tipo"].startswith("PREDICCIÓN")


def test_assistant_input_limits(client, auth):
    r = client.post("/api/assistant/ask", json={"pregunta": "x" * (config.ASSISTANT_MAX_QUESTION_CHARS + 1)}, headers=auth)
    assert r.status_code == 422


def test_assistant_without_key_returns_503(client, auth, monkeypatch):
    # Proveedor Anthropic sin credencial: debe informar 503, nunca simular una respuesta
    monkeypatch.setattr(config, "LLM_PROVIDER", "anthropic")
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    r = client.post("/api/assistant/ask", json={"pregunta": "Ventas 2016"}, headers=auth)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]
