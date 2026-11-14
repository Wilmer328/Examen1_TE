"""Integración del asistente con Ollama (proveedor local).

Las pruebas usan un servidor Ollama SIMULADO (httpx.MockTransport) para ser deterministas; las herramientas sí se
ejecutan de verdad contra el Data Warehouse a través de run_tool(). La prueba marcada 'ollama_real' usa el servicio
real si está disponible (se omite si no lo está)."""
import json

import httpx
import pytest

from common import config, db
from generative_ai import assistant
from generative_ai.verification import unverified_numbers, verify


@pytest.fixture(autouse=True)
def _ollama_provider(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(config, "OLLAMA_TOOL_MODE", "json")


def fake_ollama(monkeypatch, replies: list, seen: list | None = None):
    """Simula /api/chat devolviendo 'replies' en orden; registra los cuerpos recibidos en 'seen'."""
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": config.OLLAMA_MODEL, "model": config.OLLAMA_MODEL}]})
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body)
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json={"message": {"role": "assistant", "content": reply}, "done_reason": "stop",
                                         "prompt_eval_count": 10, "eval_count": 5})

    monkeypatch.setattr(assistant, "_http_client",
                        lambda timeout: httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout))


def plan(tool: str, params: dict) -> str:
    return json.dumps({"herramienta": tool, "parametros": params})


# ------------------------------------------------------------------ formato de herramientas
def test_ollama_tools_are_generated_from_single_tool_list():
    tools = assistant.ollama_tools()
    assert [t["function"]["name"] for t in tools] == [t["name"] for t in assistant.TOOLS]
    assert len(tools) == 7
    for o, t in zip(tools, assistant.TOOLS):
        assert o["type"] == "function" and o["function"]["parameters"] is t["input_schema"]
    enum = assistant._planner_schema()["properties"]["herramienta"]["enum"]
    assert enum == [t["name"] for t in assistant.TOOLS] + ["ninguna"]


# ------------------------------------------------------------------ flujo real por run_tool
def test_tool_call_goes_through_run_tool_and_answer_is_verified(monkeypatch):
    calls = []
    original = assistant.run_tool
    monkeypatch.setattr(assistant, "run_tool", lambda n, a: (calls.append((n, a)), original(n, a))[1])
    truth = db.scalar(db.connect(config.DB_DW), "SELECT SUM(NetAmount) FROM dw.FactSales WHERE DateKey BETWEEN 20160101 AND 20160331")
    seen = []
    fake_ollama(monkeypatch, [plan("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31"}),
                              f"[DATO] Ventas netas 2016-Q1: {float(truth):,.2f} USD."], seen)
    r = assistant.ask("Ventas netas del primer trimestre de 2016", "pytest")
    assert calls == [("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31"})]
    assert r["estado"] == "ok" and r["verificacion"]["nivel"] == "verificada"
    assert r["proveedor"] == "ollama" and r["herramientas_usadas"][0]["filas"] == 1
    # Límites de memoria enviados a Ollama y salida estructurada en la planificación
    assert all(b["options"]["num_ctx"] == config.OLLAMA_NUM_CTX for b in seen)
    assert seen[0]["format"]["properties"]["herramienta"]["enum"][-1] == "ninguna"
    assert seen[1]["options"]["num_predict"] == config.OLLAMA_NUM_PREDICT


def test_unknown_tool_is_rejected_and_never_executes_sql(monkeypatch):
    executed = []
    monkeypatch.setattr(assistant.analytics, "_q", lambda *a, **k: executed.append(a) or [])
    content, is_err = assistant._execute_tool_call("ejecutar_sql", {"sql": "DROP TABLE dw.FactSales"}, trace := [], [])
    assert is_err and "Herramienta no permitida" in content and trace[0]["error"]
    assert executed == []


def test_unknown_tool_in_native_mode_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_TOOL_MODE", "native")
    tool_call = httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "ejecutar_sql", "arguments": {"sql": "SELECT * FROM sys.tables"}}}]}, "done_reason": "stop"})
    fake_ollama(monkeypatch, [tool_call, "No tengo datos suficientes para responder eso."])
    r = assistant.ask("Borra la tabla de ventas", "pytest")
    assert r["herramientas_usadas"][0]["herramienta"] == "ejecutar_sql"
    assert "Herramienta no permitida" in r["herramientas_usadas"][0]["error"]


def test_invented_filters_are_dropped_and_invalid_values_rejected(monkeypatch):
    fake_ollama(monkeypatch, [plan("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31",
                                                    "territorio": "Plains", "categoria": "Todos los productos"}),
                              "[DATO] respuesta"])
    r = assistant.ask("Ventas netas de 2016-Q1", "pytest")
    t = r["herramientas_usadas"][0]
    assert t["parametros"] == {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31"}
    assert t["filtros_descartados"]["territorio"] == "Plains"
    with pytest.raises(assistant.analytics.ValidationError):
        assistant.run_tool("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31", "territorio": "Europe"})


def test_validation_error_is_fed_back_to_planner(monkeypatch):
    seen = []
    fake_ollama(monkeypatch, [plan("obtener_kpis", {"fecha_inicio": "ayer", "fecha_fin": "hoy"}),
                              plan("obtener_kpis", {"fecha_inicio": "2015-01-01", "fecha_fin": "2015-12-31"}),
                              "[DATO] ok"], seen)
    r = assistant.ask("Ventas de 2015", "pytest")
    assert [("error" in t) for t in r["herramientas_usadas"]] == [True, False]
    assert "rechazada" in seen[1]["messages"][1]["content"]


# ------------------------------------------------------------------ Ollama no disponible
def test_ollama_down_returns_503_with_clear_message(client, auth, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:9")   # puerto cerrado: conexión real rechazada
    st = assistant.status()
    assert st["configurado"] is False and "No se pudo conectar con Ollama" in st["detalle"]
    r = client.post("/api/assistant/ask", json={"pregunta": "Ventas de 2016"}, headers=auth)
    assert r.status_code == 503 and "Ollama" in r.json()["detail"]


def test_ollama_timeout_is_reported(monkeypatch):
    fake_ollama(monkeypatch, [httpx.ReadTimeout("timeout")])
    with pytest.raises(assistant.AssistantUnavailable, match="no respondió"):
        assistant.ask("Ventas de 2016", "pytest")


def test_model_not_downloaded_is_reported(monkeypatch):
    fake_ollama(monkeypatch, [httpx.Response(404, json={"error": "model not found"})])
    with pytest.raises(assistant.AssistantNotConfigured, match="ollama pull"):
        assistant.ask("Ventas de 2016", "pytest")


def test_failures_are_logged_for_audit(monkeypatch):
    fake_ollama(monkeypatch, [httpx.ConnectError("refused")])
    with pytest.raises(assistant.AssistantUnavailable):
        assistant.ask("Pregunta de auditoría pytest-ollama-caido", "pytest")
    row = db.query_records(db.connect(config.DB_DW), "SELECT TOP 1 Status, Model, ErrorDetail FROM ai.AssistantLog"
                                                     " WHERE Question = 'Pregunta de auditoría pytest-ollama-caido' ORDER BY LogID DESC")[0]
    assert row["Status"] == "AssistantUnavailable" and row["Model"].startswith("ollama:") and "Ollama" in row["ErrorDetail"]


# ------------------------------------------------------------------ verificación de cifras
def test_unverified_numbers_produce_warning(monkeypatch):
    fake_ollama(monkeypatch, [plan("obtener_kpis", {"fecha_inicio": "2016-01-01", "fecha_fin": "2016-03-31"}),
                              "[DATO] Ventas netas: 98,765,432.10 USD"])
    r = assistant.ask("Ventas netas de 2016-Q1", "pytest")
    assert r["estado"] == "ok_con_advertencias" and "987654" in r["verificacion"]["cifras_no_verificadas"]
    assert "Verificación automática" in r["respuesta"]


def test_numbers_without_any_query_are_flagged():
    v = verify("Las ventas fueron 1,234,567 USD", [], successful_tools=0)
    assert v["nivel"] == "sin_respaldo" and v["advertencia"]


def test_verification_accepts_rounding_and_ignores_years():
    payload = json.dumps({"ventas_netas": 13098576.8})
    assert unverified_numbers("En 2016 se vendieron 13,098,576.80 USD (≈ 13.1 millones)", [payload]) == []


# ------------------------------------------------------------------ ayudas deterministas
def test_last_complete_periods():
    assert assistant.last_complete_periods("2016-06-07")[0].startswith("2016-Q1")
    assert assistant.last_complete_periods("2016-06-07")[1].startswith("2016-05")
    assert assistant.last_complete_periods("2016-03-31")[0].startswith("2016-Q1")
    assert assistant.last_complete_periods("2016-01-15")[0].startswith("2015-Q4")


def test_forecast_answers_get_deterministic_prediction_label(monkeypatch):
    fake_ollama(monkeypatch, [plan("pronostico", {"territorio": "Southeast"}), "Pronóstico Southeast [DATO]"])
    r = assistant.ask("Pronóstico de ventas para el territorio Southeast", "pytest")
    version = db.scalar(db.connect(config.DB_DW), "SELECT ModelVersion FROM ml.ModelRegistry WHERE IsActive = 1")
    assert f"[PREDICCIÓN] Las cifras de pronóstico provienen del modelo de ML {version}" in r["respuesta"]


# ------------------------------------------------------------------ servicio real (opcional)
@pytest.mark.skipif(not assistant.is_configured(), reason="Ollama real no disponible")
def test_real_ollama_answers_with_dw_data():
    r = assistant.ask("¿Cuáles fueron las ventas netas del primer trimestre de 2016?", "pytest-real")
    truth = float(db.scalar(db.connect(config.DB_DW), "SELECT SUM(NetAmount) FROM dw.FactSales WHERE DateKey BETWEEN 20160101 AND 20160331"))
    assert any(t["herramienta"] == "obtener_kpis" and "error" not in t for t in r["herramientas_usadas"])
    assert f"{truth:,.0f}"[:6].replace(",", "") in r["respuesta"].replace(",", "").replace(".", "")
