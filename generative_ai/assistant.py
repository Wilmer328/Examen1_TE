"""Asistente analítico en lenguaje natural con Claude (API de Anthropic).

Arquitectura segura:
  usuario -> API (JWT + rate limit + validación) -> Claude con HERRAMIENTAS ANALÍTICAS LIMITADAS
  -> common.analytics (consultas parametrizadas sobre la vista aprobada del DW) -> respuesta con fuentes.
El modelo NUNCA escribe ni ejecuta SQL: solo elige herramientas de una lista blanca con parámetros validados.
A Claude solo se envían AGREGADOS (montos, conteos); no se envían datos personales de contacto.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Any

import anthropic

from common import analytics, config, db

log = logging.getLogger("genai")

SYSTEM_PROMPT = """Eres el asistente analítico de la plataforma de datos de Wide World Importers (ventas mayoristas).
Respondes en español a analistas del negocio.

Reglas obligatorias:
1. Toda cifra que menciones debe provenir de una herramienta llamada en esta conversación. Nunca inventes ni estimes cifras.
2. Antes de responder sobre ventas, llama a `estado_datos` si no conoces el rango de fechas disponible; los datos son históricos
   (2013 en adelante) y "el último trimestre" o "el último mes" se refieren al último período con datos, no al calendario actual.
3. Cita siempre el período y la métrica que respaldan cada afirmación (por ejemplo: "ventas netas 2016-Q1, sin impuesto").
4. Distingue explícitamente tres tipos de contenido con estas etiquetas:
   [DATO] cifras consultadas del Data Warehouse, [PREDICCIÓN] salidas del modelo de pronóstico (indica versión y horizonte),
   [INTERPRETACIÓN] tu análisis o recomendación.
5. Si las herramientas no devuelven datos suficientes, o la pregunta está fuera del alcance (ventas, clientes, productos,
   territorios, pronósticos, alertas), responde claramente: "No tengo datos suficientes para responder eso" y explica qué sí puedes responder.
6. Si la pregunta es ambigua, elige la interpretación más razonable, dila explícitamente y ofrece la alternativa.
7. Ventas netas = importe sin impuesto (Quantity x UnitPrice). Margen % = ganancia / ventas netas.
8. Sé conciso: máximo ~200 palabras, usa viñetas cuando ayuden."""

_DATE = {"type": "string", "description": "Fecha ISO YYYY-MM-DD"}
_FILTERS = {
    "territorio": {"type": "string", "description": "Territorio de venta, p. ej. 'Southeast', 'Far West'"},
    "categoria": {"type": "string", "description": "Categoría de producto, p. ej. 'Clothing', 'Novelty Items'"},
    "categoria_cliente": {"type": "string", "description": "Categoría de cliente, p. ej. 'Novelty Shop', 'Supermarket'"},
}

TOOLS = [
    {"name": "estado_datos",
     "description": "Devuelve el rango de fechas con datos en el Data Warehouse y la hora de la última carga ETL exitosa. "
                    "Úsala para conocer qué períodos existen antes de consultar.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "obtener_kpis",
     "description": "KPIs de ventas para un período (ventas netas, ganancia, margen %, facturas, unidades, ticket promedio, "
                    "clientes activos) y su variación % contra el período anterior de igual duración.",
     "input_schema": {"type": "object", "properties": {"fecha_inicio": _DATE, "fecha_fin": _DATE, **_FILTERS},
                      "required": ["fecha_inicio", "fecha_fin"], "additionalProperties": False}},
    {"name": "ventas_por_dimension",
     "description": "Ranking de ventas netas, ganancia y participación % por una dimensión en un período.",
     "input_schema": {"type": "object", "properties": {
         "dimension": {"type": "string", "enum": list(analytics.DIMENSIONS)},
         "fecha_inicio": _DATE, "fecha_fin": _DATE, "top_n": {"type": "integer", "minimum": 1, "maximum": 20}, **_FILTERS},
         "required": ["dimension", "fecha_inicio", "fecha_fin"], "additionalProperties": False}},
    {"name": "tendencia",
     "description": "Serie temporal de ventas netas, ganancia y facturas por año, trimestre, mes o semana.",
     "input_schema": {"type": "object", "properties": {
         "granularidad": {"type": "string", "enum": list(analytics.GRAINS)}, "fecha_inicio": _DATE, "fecha_fin": _DATE,
         **_FILTERS}, "required": ["granularidad", "fecha_inicio", "fecha_fin"], "additionalProperties": False}},
    {"name": "comparar_periodos",
     "description": "Compara ventas netas de dos períodos por dimensión y devuelve los miembros con mayor cambio absoluto "
                    "y su variación %. Útil para crecimiento o caídas.",
     "input_schema": {"type": "object", "properties": {
         "dimension": {"type": "string", "enum": list(analytics.DIMENSIONS)},
         "actual_inicio": _DATE, "actual_fin": _DATE, "anterior_inicio": _DATE, "anterior_fin": _DATE,
         "top_n": {"type": "integer", "minimum": 1, "maximum": 20}, **_FILTERS},
         "required": ["dimension", "actual_inicio", "actual_fin", "anterior_inicio", "anterior_fin"], "additionalProperties": False}},
    {"name": "pronostico",
     "description": "Pronóstico (PREDICCIÓN del modelo de ML activo) de ventas netas semanales por territorio a 1-4 semanas, "
                    "con versión del modelo.",
     "input_schema": {"type": "object", "properties": {"territorio": _FILTERS["territorio"]}, "additionalProperties": False}},
    {"name": "alertas_recientes",
     "description": "Alertas recientes generadas por reglas de negocio, el modelo de ML o IA.",
     "input_schema": {"type": "object", "properties": {"limite": {"type": "integer", "minimum": 1, "maximum": 20}},
                      "additionalProperties": False}},
]


def _d(v: Any, name: str) -> date:
    try:
        return date.fromisoformat(str(v))
    except ValueError as exc:
        raise analytics.ValidationError(f"Fecha inválida en '{name}': {v}") from exc


def _filters(args: dict) -> dict:
    return {k: args[k] for k in _FILTERS if args.get(k)}


def run_tool(name: str, args: dict) -> Any:
    """Ejecuta una herramienta de la lista blanca. Cualquier otra cosa se rechaza."""
    if name == "estado_datos":
        return analytics.freshness()
    if name == "obtener_kpis":
        return analytics.kpis(analytics.Filters(_d(args["fecha_inicio"], "fecha_inicio"), _d(args["fecha_fin"], "fecha_fin"),
                                                _filters(args)))
    if name == "ventas_por_dimension":
        return analytics.breakdown(analytics.Filters(_d(args["fecha_inicio"], "fecha_inicio"), _d(args["fecha_fin"], "fecha_fin"),
                                                     _filters(args)), args["dimension"], args.get("top_n", 10))
    if name == "tendencia":
        return analytics.trend(analytics.Filters(_d(args["fecha_inicio"], "fecha_inicio"), _d(args["fecha_fin"], "fecha_fin"),
                                                 _filters(args)), args["granularidad"])
    if name == "comparar_periodos":
        return analytics.compare_periods(args["dimension"], _d(args["actual_inicio"], "actual_inicio"),
                                         _d(args["actual_fin"], "actual_fin"), _d(args["anterior_inicio"], "anterior_inicio"),
                                         _d(args["anterior_fin"], "anterior_fin"), _filters(args), args.get("top_n", 10))
    if name == "pronostico":
        return analytics.forecasts(args.get("territorio"))
    if name == "alertas_recientes":
        rows = analytics.recent_alerts(args.get("limite", 10))
        return [{k: r[k] for k in ("AlertID", "CreatedAt", "AlertType", "Severity", "Indicator", "Entity", "ObservedValue",
                                   "ThresholdValue", "PeriodStart", "PeriodEnd", "Status", "IsSimulated")} for r in rows]
    raise analytics.ValidationError(f"Herramienta no permitida: {name}")


class AssistantNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_PROFILE"))


def _client() -> anthropic.Anthropic:
    if not is_configured():
        raise AssistantNotConfigured("El asistente no está configurado: defina ANTHROPIC_API_KEY en .env")
    try:
        return anthropic.Anthropic(max_retries=2, timeout=120)
    except anthropic.AnthropicError as exc:  # credenciales inválidas
        raise AssistantNotConfigured("El asistente no está configurado: defina ANTHROPIC_API_KEY en .env") from exc


def ask(question: str, username: str, max_turns: int = 8) -> dict:
    question = (question or "").strip()
    if not question:
        raise analytics.ValidationError("La pregunta está vacía")
    if len(question) > config.ASSISTANT_MAX_QUESTION_CHARS:
        raise analytics.ValidationError(f"La pregunta supera {config.ASSISTANT_MAX_QUESTION_CHARS} caracteres")

    client = _client()
    t0 = time.perf_counter()
    messages: list = [{"role": "user", "content": question}]
    trace: list[dict] = []
    usage_in = usage_out = 0
    status, answer, model_used, error = "ok", "", config.ANTHROPIC_MODEL, None
    try:
        for _ in range(max_turns):
            resp = client.beta.messages.create(
                model=config.ANTHROPIC_MODEL, max_tokens=16000, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
                output_config={"effort": config.ASSISTANT_EFFORT},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            usage_in += resp.usage.input_tokens or 0
            usage_out += resp.usage.output_tokens or 0
            model_used = resp.model
            if resp.stop_reason == "refusal":
                status, answer = "refusal", "No puedo responder esa solicitud."
                break
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                answer = "".join(b.text for b in resp.content if b.type == "text").strip()
                if resp.stop_reason == "max_tokens":
                    status = "truncated"
                break
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                entry = {"herramienta": block.name, "parametros": block.input}
                try:
                    data = run_tool(block.name, dict(block.input or {}))
                    payload = json.dumps(data, default=str, ensure_ascii=False)
                    entry["filas"] = len(data) if isinstance(data, list) else 1
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": payload[:60000]})
                except (analytics.ValidationError, KeyError) as exc:
                    entry["error"] = str(exc)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Error de validación: {exc}",
                                    "is_error": True})
                trace.append(entry)
            messages.append({"role": "user", "content": results})
        else:
            status, answer = "max_turns", "No pude completar el análisis en el número de pasos permitido."
    except anthropic.AuthenticationError as exc:
        status, error = "auth_error", str(exc)
        raise AssistantNotConfigured("Credencial de Anthropic inválida") from exc
    except anthropic.RateLimitError as exc:
        status, error = "rate_limited", str(exc)
        raise
    except anthropic.APIStatusError as exc:
        status, error = f"api_error_{exc.status_code}", str(exc)
        raise
    except anthropic.APIConnectionError as exc:
        status, error = "connection_error", str(exc)
        raise
    finally:
        latency = int((time.perf_counter() - t0) * 1000)
        _log(username, question, trace, status, len(answer), latency, usage_in, usage_out, model_used, error)

    return {"respuesta": answer, "estado": status, "herramientas_usadas": trace, "modelo": model_used,
            "latencia_ms": latency, "tokens": {"entrada": usage_in, "salida": usage_out},
            "datos_actualizados": analytics.freshness(),
            "aviso": "Respuesta generada por IA a partir de consultas al Data Warehouse. Verifique las cifras en las fuentes."}


def _log(username, question, trace, status, chars, latency, tin, tout, model, error) -> None:
    try:
        with db.connection(config.DB_DW, role="api") as cn:
            cn.cursor().execute(
                "INSERT ai.AssistantLog (Username, Question, ToolsJson, Status, AnswerChars, LatencyMs, InputTokens, OutputTokens,"
                " Model, ErrorDetail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                username, question[:600], json.dumps(trace, default=str, ensure_ascii=False)[:100000], status, chars, latency,
                tin, tout, model, (error or "")[:1000] or None)
    except Exception as exc:  # noqa: BLE001 - el log nunca debe tumbar la respuesta
        log.error("No se pudo registrar la consulta del asistente: %s", exc)


def explain_alert(alert: dict) -> str | None:
    """Explicación breve de una alerta, generada por IA y basada SOLO en los datos de la alerta y KPIs consultados."""
    try:
        client = _client()
    except AssistantNotConfigured:
        return None
    context = json.dumps({k: alert.get(k) for k in ("AlertType", "Indicator", "Entity", "ObservedValue", "ThresholdValue",
                                                    "ReferenceValue", "PeriodStart", "PeriodEnd", "Origin", "Message")},
                         default=str, ensure_ascii=False)
    try:
        resp = client.beta.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=2000, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            system=("Explicas alertas de ventas a analistas en español, en máximo 80 palabras. Usa SOLO los datos del JSON. "
                    "Incluye: qué pasó (con cifras y período), una posible causa marcada como hipótesis y una acción recomendada. "
                    "No inventes cifras."),
            messages=[{"role": "user", "content": f"Alerta: {context}"}])
        if resp.stop_reason == "refusal":
            return None
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None
    except anthropic.APIError as exc:
        log.error("No se pudo generar la explicación de la alerta: %s", exc)
        return None
