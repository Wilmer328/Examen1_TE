"""Asistente analítico en lenguaje natural con proveedor intercambiable (LLM_PROVIDER):
  - ollama    (predeterminado): modelo local, p. ej. qwen2.5:1.5b. Ningún dato sale del equipo.
  - anthropic (alternativa): Claude vía API de Anthropic.

Arquitectura segura (idéntica para ambos proveedores):
  usuario -> API (JWT + rate limit + validación) -> modelo con HERRAMIENTAS ANALÍTICAS LIMITADAS (lista única TOOLS)
  -> run_tool() (lista blanca + validación) -> common.analytics (consultas parametrizadas sobre la vista aprobada del DW)
  -> respuesta + verificación automática de cifras + fuentes.
El modelo NUNCA escribe ni ejecuta SQL: solo pide herramientas de la lista blanca; los parámetros se validan en el servidor.
Al modelo solo se envían AGREGADOS (montos, conteos); no se envían datos personales de contacto.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from typing import Any

import anthropic
import httpx

from common import analytics, config, db
from generative_ai.verification import verify

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


# Valores genéricos que los modelos pequeños suelen enviar en filtros opcionales y que significan "sin filtro".
_NO_FILTER = {"todos", "todas", "todo", "all", "any", "nacional", "total", "general", "global", "ninguno", "ninguna",
              "none", "null", "n/a", "na", "-", "*"}
_valid_cache: dict = {"t": 0.0, "values": None}


def _valid_filter_values() -> dict:
    """Valores existentes en el DW para cada filtro (caché de 5 minutos)."""
    if _valid_cache["values"] is None or time.monotonic() - _valid_cache["t"] > 300:
        _valid_cache["values"] = analytics.filter_options()
        _valid_cache["t"] = time.monotonic()
    return _valid_cache["values"]


def _filters(args: dict) -> dict:
    """Normaliza y VALIDA los filtros opcionales: valores genéricos ('todos', 'nacional'...) = sin filtro;
    valores que no existen en el DW se rechazan (evita respuestas en 0 por filtros inventados)."""
    out = {}
    for k in _FILTERS:
        v = args.get(k)
        if v is None or (isinstance(v, str) and (not v.strip() or v.strip().lower() in _NO_FILTER
                                                 or v.strip().lower().startswith(("todos ", "todas ")))):
            continue
        valid = _valid_filter_values().get(k, [])
        match = next((x for x in valid if str(x).lower() == str(v).strip().lower()), None)
        if match is None:
            raise analytics.ValidationError(f"Valor no válido para '{k}': {v}. Valores permitidos: {', '.join(map(str, valid))}. "
                                            "Omita el filtro si la pregunta no lo menciona.")
        out[k] = match
    return out


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
        return analytics.forecasts(_filters({"territorio": args.get("territorio")}).get("territorio"))
    if name == "alertas_recientes":
        rows = analytics.recent_alerts(args.get("limite", 10))
        return [{k: r[k] for k in ("AlertID", "CreatedAt", "AlertType", "Severity", "Indicator", "Entity", "ObservedValue",
                                   "ThresholdValue", "PeriodStart", "PeriodEnd", "Status", "IsSimulated")} for r in rows]
    raise analytics.ValidationError(f"Herramienta no permitida: {name}")


class AssistantNotConfigured(RuntimeError):
    """El proveedor no está configurado (p. ej. falta API key o el modelo no está descargado)."""


class AssistantUnavailable(RuntimeError):
    """El proveedor está configurado pero no respondió (servicio caído, tiempo de espera, error HTTP)."""


# Prompt de sistema compacto para modelos locales pequeños: en pruebas, el prompt largo en español inhibía las
# llamadas a herramientas de qwen2.5:1.5b. Las reglas de seguridad NO dependen del prompt: las aplica run_tool().
OLLAMA_SYSTEM_PROMPT = """Eres un asistente de análisis de ventas de Wide World Importers. Responde siempre en español.
Datos disponibles en el Data Warehouse: desde {desde} hasta {hasta}. "Último trimestre", "último mes" o "último año" se refieren
a ese rango, no al calendario actual.
Reglas:
- Para cualquier pregunta sobre ventas, ganancias, clientes, productos, territorios, pronósticos o alertas, LLAMA A UNA
  HERRAMIENTA antes de responder. Usa fechas en formato YYYY-MM-DD.
- Usa solo cifras que devuelvan las herramientas. No inventes números.
- Indica el período y la métrica de cada cifra. Marca cifras consultadas con [DATO], pronósticos con [PREDICCIÓN] y tu
  análisis con [INTERPRETACIÓN].
- Si la pregunta no trata de estos datos (por ejemplo empleados, salarios, Europa, fechas sin datos) responde:
  "No tengo datos suficientes para responder eso." y explica qué sí puedes responder.
- No ejecutas SQL ni modificas datos. Responde en menos de 150 palabras."""


def provider() -> str:
    return config.LLM_PROVIDER


def model_name() -> str:
    return config.OLLAMA_MODEL if provider() == "ollama" else config.ANTHROPIC_MODEL


def _http_client(timeout: float) -> httpx.Client:
    """Fábrica del cliente HTTP (reemplazable en pruebas)."""
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=5.0))


def ollama_status() -> dict:
    """Comprueba que el servicio Ollama responda y que el modelo configurado esté descargado (sin cargarlo en memoria)."""
    try:
        with _http_client(5.0) as http:
            r = http.get(f"{config.OLLAMA_BASE_URL}/api/tags")
        r.raise_for_status()
        names = {m.get("name") for m in r.json().get("models", [])} | {m.get("model") for m in r.json().get("models", [])}
        if config.OLLAMA_MODEL not in names:
            return {"disponible": True, "modelo_descargado": False,
                    "detalle": f"Ollama responde pero el modelo '{config.OLLAMA_MODEL}' no está descargado. "
                               f"Ejecute: ollama pull {config.OLLAMA_MODEL}"}
        return {"disponible": True, "modelo_descargado": True, "detalle": "ok"}
    except httpx.HTTPError as exc:
        return {"disponible": False, "modelo_descargado": False,
                "detalle": f"No se pudo conectar con Ollama en {config.OLLAMA_BASE_URL} ({type(exc).__name__}). "
                           "Inicie Ollama (aplicación de escritorio o 'ollama serve')."}


def _anthropic_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_PROFILE"))


def is_configured() -> bool:
    if provider() == "ollama":
        s = ollama_status()
        return s["disponible"] and s["modelo_descargado"]
    return _anthropic_configured()


def status() -> dict:
    if provider() == "ollama":
        s = ollama_status()
        return {"proveedor": "ollama", "modelo": config.OLLAMA_MODEL, "configurado": s["disponible"] and s["modelo_descargado"],
                "detalle": s["detalle"], "url": config.OLLAMA_BASE_URL}
    ok = _anthropic_configured()
    return {"proveedor": "anthropic", "modelo": config.ANTHROPIC_MODEL, "configurado": ok,
            "detalle": "ok" if ok else "Defina ANTHROPIC_API_KEY en .env"}


def ollama_tools() -> list[dict]:
    """Formato de herramientas de Ollama GENERADO desde la lista única TOOLS (no se duplican definiciones)."""
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in TOOLS]


def _execute_tool_call(name: Any, raw_args: Any, trace: list, payloads: list) -> tuple[str, bool]:
    """Ejecuta UNA llamada pedida por el modelo, SIEMPRE a través de run_tool() (lista blanca + validación).
    Devuelve (contenido para el modelo, es_error)."""
    entry: dict = {"herramienta": str(name), "parametros": raw_args}
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args if raw_args is not None else {})
        if not isinstance(args, dict):
            raise analytics.ValidationError("Los parámetros de la herramienta deben ser un objeto JSON")
        entry["parametros"] = args
        data = run_tool(str(name), dict(args))
        payload = json.dumps(data, default=str, ensure_ascii=False)
        limit = config.ASSISTANT_TOOL_RESULT_MAX_CHARS
        if len(payload) > limit:
            payload = payload[:limit] + ' ... [resultado recortado; pida menos filas con top_n o un período más corto]'
            entry["recortado"] = True
        entry["filas"] = len(data) if isinstance(data, list) else 1
        payloads.append(payload)
        trace.append(entry)
        return payload, False
    except (analytics.ValidationError, KeyError, TypeError, ValueError) as exc:
        entry["error"] = str(exc)
        trace.append(entry)
        return f"Error de validación: {exc}", True


def _ask_anthropic(question: str, trace: list, payloads: list, max_turns: int) -> dict:
    if not _anthropic_configured():
        raise AssistantNotConfigured("El asistente no está configurado: defina ANTHROPIC_API_KEY en .env")
    client = anthropic.Anthropic(max_retries=2, timeout=120)
    messages: list = [{"role": "user", "content": question}]
    out = {"answer": "", "status": "ok", "model": config.ANTHROPIC_MODEL, "tin": 0, "tout": 0}
    try:
        for _ in range(max_turns):
            resp = client.beta.messages.create(
                model=config.ANTHROPIC_MODEL, max_tokens=16000, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
                output_config={"effort": config.ASSISTANT_EFFORT},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            out["tin"] += resp.usage.input_tokens or 0
            out["tout"] += resp.usage.output_tokens or 0
            out["model"] = resp.model
            if resp.stop_reason == "refusal":
                out.update(status="refusal", answer="No puedo responder esa solicitud.")
                return out
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                out["answer"] = "".join(b.text for b in resp.content if b.type == "text").strip()
                if resp.stop_reason == "max_tokens":
                    out["status"] = "truncated"
                return out
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    content, is_err = _execute_tool_call(block.name, block.input, trace, payloads)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": content,
                                    **({"is_error": True} if is_err else {})})
            messages.append({"role": "user", "content": results})
        out.update(status="max_turns", answer="No pude completar el análisis en el número de pasos permitido.")
        return out
    except anthropic.AuthenticationError as exc:
        raise AssistantNotConfigured("Credencial de Anthropic inválida") from exc
    except anthropic.APIConnectionError as exc:
        raise AssistantUnavailable(f"No se pudo conectar con la API de Anthropic: {exc}") from exc


def _ollama_chat(http: httpx.Client, messages: list, tools: list | None, num_predict: int, fmt: dict | None = None) -> dict:
    body = {"model": config.OLLAMA_MODEL, "messages": messages, "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": {"num_ctx": config.OLLAMA_NUM_CTX, "num_predict": num_predict, "temperature": 0}}
    if tools:
        body["tools"] = tools
    if fmt:
        body["format"] = fmt   # salida estructurada: Ollama restringe la generación a este esquema JSON
    try:
        r = http.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=body)
    except httpx.ConnectError as exc:
        raise AssistantUnavailable(f"No se pudo conectar con Ollama en {config.OLLAMA_BASE_URL}. "
                                   "Verifique que Ollama esté en ejecución.") from exc
    except httpx.TimeoutException as exc:
        raise AssistantUnavailable(f"Ollama no respondió dentro de {config.OLLAMA_TIMEOUT:.0f} s "
                                   f"(modelo {config.OLLAMA_MODEL}). Intente una pregunta más simple o aumente OLLAMA_TIMEOUT.") from exc
    except httpx.HTTPError as exc:
        raise AssistantUnavailable(f"Error de comunicación con Ollama: {type(exc).__name__}") from exc
    if r.status_code == 404:
        raise AssistantNotConfigured(f"Ollama no encontró el modelo '{config.OLLAMA_MODEL}'. Ejecute: ollama pull {config.OLLAMA_MODEL}")
    if r.status_code >= 400:
        raise AssistantUnavailable(f"Ollama devolvió HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except ValueError as exc:
        raise AssistantUnavailable("Ollama devolvió una respuesta que no es JSON") from exc


PLANNER_PROMPT = """Eliges UNA herramienta de datos para responder la pregunta de un analista de ventas de Wide World Importers.
Datos disponibles: {desde} a {hasta}. Último trimestre completo con datos: {ult_trim}. Último mes completo: {ult_mes}.
"Último trimestre" o "último mes" se refieren a esos períodos. Si la pregunta es general (p. ej. "¿cómo van las ventas?"),
usa obtener_kpis del último trimestre completo.
Trimestres: Q1 = MM-DD 01-01 a 03-31, Q2 = 04-01 a 06-30, Q3 = 07-01 a 09-30, Q4 = 10-01 a 12-31. Fechas en formato YYYY-MM-DD.
Herramientas:
{catalogo}
Reglas:
- Incluye territorio, categoria o categoria_cliente SOLO si la pregunta los nombra explícitamente; si no, omítelos.
- Para rankings (mejores clientes, productos, categorías) usa ventas_por_dimension. Para crecimiento o caídas entre dos
  períodos usa comparar_periodos (actual = el período más reciente). Para totales de un período usa obtener_kpis.
- Si la pregunta no trata de ventas, clientes, productos, territorios, pronósticos o alertas de este negocio, o pide fechas
  fuera del rango disponible, elige "ninguna".
Ejemplos:
P: Ventas del 2015-Q3 -> {{"herramienta":"obtener_kpis","parametros":{{"fecha_inicio":"2015-07-01","fecha_fin":"2015-09-30"}}}}
P: Top 5 productos de 2014 -> {{"herramienta":"ventas_por_dimension","parametros":{{"dimension":"producto","fecha_inicio":"2014-01-01","fecha_fin":"2014-12-31","top_n":5}}}}
P: ¿Qué territorios crecieron en 2016-Q1 frente a 2015-Q1? -> {{"herramienta":"comparar_periodos","parametros":{{"dimension":"territorio","actual_inicio":"2016-01-01","actual_fin":"2016-03-31","anterior_inicio":"2015-01-01","anterior_fin":"2015-03-31"}}}}
P: Tendencia mensual de 2015 en Plains -> {{"herramienta":"tendencia","parametros":{{"granularidad":"mes","fecha_inicio":"2015-01-01","fecha_fin":"2015-12-31","territorio":"Plains"}}}}
P: ¿Cuál es el clima en Madrid? -> {{"herramienta":"ninguna","parametros":{{}}}}"""

ANSWER_PROMPT = """Eres un asistente de análisis de ventas. Responde en español, en menos de 150 palabras.
Usa ÚNICAMENTE las cifras que aparecen en los RESULTADOS; no inventes ni calcules cifras nuevas salvo porcentajes simples.
Indica período y métrica de cada cifra. Marca las cifras consultadas con [DATO], los pronósticos con [PREDICCIÓN] y tu
análisis con [INTERPRETACIÓN]. ventas_netas, ganancia y ticket_promedio son montos en USD (sin impuestos);
unidades es cantidad de artículos; facturas es cantidad de facturas; participacion_pct y variacion_pct son porcentajes.
Si no hay resultados o no responden la pregunta, contesta exactamente: "No tengo datos suficientes para responder eso." y
explica brevemente qué sí puedes responder (ventas, clientes, productos, territorios, pronósticos y alertas de 2013 a 2016)."""


def last_complete_periods(hasta: str) -> tuple[str, str]:
    """Último trimestre y último mes COMPLETOS dentro del rango de datos (cálculo determinista, no del modelo)."""
    end = date.fromisoformat(str(hasta)[:10])
    y, q = end.year, (end.month - 1) // 3 + 1
    q_end_month = q * 3
    q_last_day = (date(y + (q_end_month == 12), q_end_month % 12 + 1, 1) - timedelta(days=1))
    if end < q_last_day:                    # el trimestre actual está incompleto -> el anterior
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    q_start = date(y, 3 * (q - 1) + 1, 1)
    q_stop = date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1)
    month_first = date(end.year, end.month, 1)
    if (end + timedelta(days=1)).month == end.month:   # el mes actual está incompleto -> el anterior
        month_first = (month_first - timedelta(days=1)).replace(day=1)
    month_last = (month_first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return (f"{y}-Q{q} ({q_start} a {q_stop})", f"{month_first:%Y-%m} ({month_first} a {month_last})")


def _prediction_note(trace: list, payloads: list) -> str | None:
    """Etiqueta determinista: si se consultó el pronóstico, se agrega quién lo produjo (no depende del modelo de lenguaje)."""
    if not any(t["herramienta"] == "pronostico" and "error" not in t for t in trace):
        return None
    version = "desconocida"
    for p in payloads:
        try:
            version = json.loads(p).get("modelo", {}).get("version") or version
        except (ValueError, AttributeError):
            continue
    return (f"[PREDICCIÓN] Las cifras de pronóstico provienen del modelo de ML {version} (horizonte de 1 a 4 semanas); "
            "son predicciones, no datos históricos.")


def _planner_schema() -> dict:
    """Esquema de salida estructurada GENERADO desde la lista única TOOLS (enum de nombres + 'ninguna')."""
    return {"type": "object",
            "properties": {"herramienta": {"type": "string", "enum": [t["name"] for t in TOOLS] + ["ninguna"]},
                           "parametros": {"type": "object"}},
            "required": ["herramienta", "parametros"]}


def _tool_catalog() -> str:
    return "\n".join(f"- {t['name']}: {t['description']} Parámetros: "
                     f"{json.dumps(t['input_schema'].get('properties', {}), ensure_ascii=False)}"
                     f" Obligatorios: {t['input_schema'].get('required', [])}" for t in TOOLS)


def _ask_ollama_json(question: str, trace: list, payloads: list, max_turns: int, http: httpx.Client, rng: dict) -> dict:
    """Modo para modelos pequeños: 1) planificación con salida JSON restringida (elige herramienta y parámetros),
    2) ejecución vía run_tool(), 3) redacción de la respuesta SOLO con los resultados obtenidos.
    Ante un error de validación, el error se devuelve al planificador para que corrija (hasta max_turns - 1 intentos)."""
    out = {"answer": "", "status": "ok", "model": config.OLLAMA_MODEL, "tin": 0, "tout": 0}
    q_label, m_label = last_complete_periods(rng["hasta"])
    planner = PLANNER_PROMPT.format(desde=rng["desde"], hasta=rng["hasta"], ult_trim=q_label, ult_mes=m_label,
                                    catalogo=_tool_catalog())
    feedback, results, seen = "", [], set()
    for _ in range(max(1, max_turns - 1)):
        data = _ollama_chat(http, [{"role": "system", "content": planner},
                                   {"role": "user", "content": question + feedback}], None, 300, fmt=_planner_schema())
        out["tin"] += int(data.get("prompt_eval_count") or 0)
        out["tout"] += int(data.get("eval_count") or 0)
        try:
            plan = json.loads((data.get("message") or {}).get("content") or "{}")
        except ValueError:
            trace.append({"herramienta": "(plan inválido)", "parametros": None, "error": "El modelo no devolvió JSON válido"})
            break
        name, params = plan.get("herramienta"), plan.get("parametros") or {}
        if name == "ninguna" or not name:
            break
        key = (name, json.dumps(params, sort_keys=True, default=str))
        if key in seen:        # el modelo repite la misma llamada: no insistir
            break
        seen.add(key)
        # Guardia determinista: un filtro opcional solo se aplica si su valor aparece en la pregunta del usuario.
        # Los modelos pequeños tienden a rellenar filtros con ejemplos de las descripciones (respuestas sobre subconjuntos).
        dropped = {k: params.pop(k) for k in list(params) if k in _FILTERS and isinstance(params[k], str)
                   and params[k].strip() and params[k].strip().lower() not in question.lower()}
        content, is_err = _execute_tool_call(name, params, trace, payloads)
        if dropped:
            trace[-1]["filtros_descartados"] = dropped
        if not is_err:
            results.append({"herramienta": name, "parametros": params, "resultado": content})
            break
        feedback = (f"\n\n[Intento anterior: herramienta {name} con {json.dumps(params, ensure_ascii=False)} fue rechazada: "
                    f"{content}. Corrige los parámetros o elige otra herramienta.]")

    if results:
        context = "\n".join(f"RESULTADOS de {r['herramienta']} {json.dumps(r['parametros'], ensure_ascii=False)}:\n{r['resultado']}"
                            for r in results)
    else:
        context = "RESULTADOS: ninguno (no se consultó el Data Warehouse para esta pregunta)."
    data = _ollama_chat(http, [{"role": "system", "content": ANSWER_PROMPT},
                               {"role": "user", "content": f"Pregunta: {question}\n\n{context}"}], None, config.OLLAMA_NUM_PREDICT)
    out["tin"] += int(data.get("prompt_eval_count") or 0)
    out["tout"] += int(data.get("eval_count") or 0)
    out["answer"] = ((data.get("message") or {}).get("content") or "").strip()
    if data.get("done_reason") == "length":
        out["status"] = "truncated"
    if not out["answer"]:
        out.update(status="empty", answer="El modelo no generó una respuesta.")
    return out


def _ask_ollama(question: str, trace: list, payloads: list, max_turns: int) -> dict:
    rng = analytics.data_range()
    if config.OLLAMA_TOOL_MODE != "native":
        with _http_client(config.OLLAMA_TIMEOUT) as http:
            return _ask_ollama_json(question, trace, payloads, max_turns, http, rng)
    # Modo "native": llamadas a herramientas nativas de Ollama (mejor con modelos más grandes)
    messages: list = [{"role": "system", "content": OLLAMA_SYSTEM_PROMPT.format(desde=rng["desde"], hasta=rng["hasta"])},
                      {"role": "user", "content": question}]
    out = {"answer": "", "status": "ok", "model": config.OLLAMA_MODEL, "tin": 0, "tout": 0}
    tools = ollama_tools()
    with _http_client(config.OLLAMA_TIMEOUT) as http:
        for turn in range(max_turns):
            last = turn == max_turns - 1
            # En el último turno no se ofrecen herramientas: el modelo debe responder con lo ya consultado.
            data = _ollama_chat(http, messages, None if last else tools, config.OLLAMA_NUM_PREDICT)
            out["tin"] += int(data.get("prompt_eval_count") or 0)
            out["tout"] += int(data.get("eval_count") or 0)
            msg = data.get("message") or {}
            calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})})
            if not calls:
                out["answer"] = (msg.get("content") or "").strip()
                if data.get("done_reason") == "length":
                    out["status"] = "truncated"
                if not out["answer"]:
                    out.update(status="empty", answer="El modelo no generó una respuesta.")
                return out
            for c in calls:
                fn = c.get("function") or {}
                content, _ = _execute_tool_call(fn.get("name"), fn.get("arguments"), trace, payloads)
                messages.append({"role": "tool", "tool_name": str(fn.get("name")), "content": content})
    out.update(status="max_turns", answer="No pude completar el análisis en el número de pasos permitido.")
    return out


def ask(question: str, username: str, max_turns: int | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        raise analytics.ValidationError("La pregunta está vacía")
    if len(question) > config.ASSISTANT_MAX_QUESTION_CHARS:
        raise analytics.ValidationError(f"La pregunta supera {config.ASSISTANT_MAX_QUESTION_CHARS} caracteres")
    max_turns = max_turns or config.ASSISTANT_MAX_TURNS

    t0 = time.perf_counter()
    trace: list[dict] = []
    payloads: list[str] = []
    result = {"answer": "", "status": "error", "model": model_name(), "tin": 0, "tout": 0}
    error = None
    verification: dict | None = None
    try:
        result = (_ask_ollama if provider() == "ollama" else _ask_anthropic)(question, trace, payloads, max_turns)
        successful = sum(1 for t in trace if "error" not in t)
        verification = verify(result["answer"], payloads, successful)
        if result["status"] == "ok" and verification["advertencia"]:
            result["status"] = "ok_con_advertencias"
            result["answer"] += f"\n\n⚠ Verificación automática: {verification['advertencia']}"
        note = _prediction_note(trace, payloads)
        if note:
            result["answer"] += f"\n\n{note}"
    except (AssistantNotConfigured, AssistantUnavailable) as exc:
        result["status"], error = type(exc).__name__, str(exc)
        raise
    except Exception as exc:  # noqa: BLE001 - se registra y se propaga
        result["status"], error = "error", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        latency = int((time.perf_counter() - t0) * 1000)
        _log(username, question, trace, result["status"], len(result["answer"]), latency, result["tin"], result["tout"],
             f"{provider()}:{result['model']}", error)

    return {"respuesta": result["answer"], "estado": result["status"], "herramientas_usadas": trace,
            "proveedor": provider(), "modelo": result["model"], "latencia_ms": latency,
            "tokens": {"entrada": result["tin"], "salida": result["tout"]}, "verificacion": verification,
            "datos_actualizados": analytics.freshness(),
            "aviso": "Respuesta generada por IA a partir de consultas al Data Warehouse. Verifique las cifras en las fuentes."}


def _log(username, question, trace, status, chars, latency, tin, tout, model, error) -> None:
    try:
        with db.connection(config.DB_DW, role="api") as cn:
            cn.cursor().execute(
                "INSERT ai.AssistantLog (Username, Question, ToolsJson, Status, AnswerChars, LatencyMs, InputTokens, OutputTokens,"
                " Model, ErrorDetail) VALUES (?,?,?,?,?,?,?,?,?,?)",
                username, question[:600], json.dumps(trace, default=str, ensure_ascii=False)[:100000], status[:30], chars,
                latency, tin, tout, model[:60], (error or "")[:1000] or None)
    except Exception as exc:  # noqa: BLE001 - el log nunca debe tumbar la respuesta
        log.error("No se pudo registrar la consulta del asistente: %s", exc)


ALERT_PROMPT = ("Explicas alertas de ventas a analistas en español, en máximo 80 palabras. Usa SOLO los datos del JSON. "
                "Incluye: qué pasó (con cifras y período), una posible causa marcada como hipótesis y una acción recomendada. "
                "No inventes cifras.")


def explain_alert(alert: dict) -> str | None:
    """Explicación breve de una alerta generada por IA, basada SOLO en los datos de la alerta.
    Devuelve None si el proveedor no está disponible (la alerta se entrega igual, sin explicación)."""
    context = json.dumps({k: alert.get(k) for k in ("AlertType", "Indicator", "Entity", "ObservedValue", "ThresholdValue",
                                                    "ReferenceValue", "PeriodStart", "PeriodEnd", "Origin", "Message")},
                         default=str, ensure_ascii=False)
    try:
        if provider() == "ollama":
            with _http_client(config.OLLAMA_TIMEOUT) as http:
                data = _ollama_chat(http, [{"role": "system", "content": ALERT_PROMPT},
                                           {"role": "user", "content": f"Alerta: {context}"}], None, 300)
            return ((data.get("message") or {}).get("content") or "").strip() or None
        if not _anthropic_configured():
            return None
        resp = anthropic.Anthropic(max_retries=2, timeout=120).beta.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=2000, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", system=ALERT_PROMPT,
            messages=[{"role": "user", "content": f"Alerta: {context}"}])
        if resp.stop_reason == "refusal":
            return None
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None
    except (AssistantNotConfigured, AssistantUnavailable, anthropic.APIError) as exc:
        log.error("No se pudo generar la explicación de la alerta: %s", exc)
        return None
