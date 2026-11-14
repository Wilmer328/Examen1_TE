"""Verificación automática (HEURÍSTICA) de cifras en respuestas generadas.

Compara los números "materiales" de la respuesta (≥ 4 dígitos significativos: montos y conteos) con los números
presentes en los datos que realmente devolvieron las herramientas del Data Warehouse en esa conversación.

Limitaciones conocidas (no es infalible):
  - Solo revisa cifras de 4 o más dígitos; porcentajes y valores pequeños no se verifican.
  - Acepta redondeos por prefijo (p. ej. "12,1 millones" vs 12093187.70 -> prefijo "121"), lo que puede dejar pasar
    un número que coincide por casualidad con el prefijo de otro.
  - Un número derivado correctamente por el modelo (suma o resta de dos resultados) se marcará como "no verificado".
  - No verifica afirmaciones cualitativas ("creció", "la mayor categoría").
"""
from __future__ import annotations

import re

NUM = re.compile(r"\d[\d.,]*\d|\d")
YEARS = {str(y) for y in range(2000, 2101)}


def _digits(token: str) -> str:
    return re.sub(r"[.,]", "", token)


def material_numbers(text: str) -> set[str]:
    """Primeros 6 dígitos de cada número con ≥ 4 dígitos (se ignoran años 2000-2100)."""
    out = set()
    for m in NUM.findall(text or ""):
        d = _digits(m)
        if len(d) >= 4 and d not in YEARS:
            out.add(d[:6])
    return out


def supported_prefixes(payloads: list[str]) -> set[str]:
    """Prefijos (2..6 dígitos) de la parte entera y del número completo de cada valor devuelto por las herramientas."""
    support: set[str] = set()
    for p in payloads:
        for m in NUM.findall(p):
            for variant in (_digits(m), _digits(m.split(".")[0])):
                for k in range(2, min(len(variant), 6) + 1):
                    support.add(variant[:k])
    return support


def unverified_numbers(answer: str, tool_payloads: list[str]) -> list[str]:
    support = supported_prefixes(tool_payloads)
    return sorted(n for n in material_numbers(answer) if n not in support)


def verify(answer: str, tool_payloads: list[str], successful_tools: int) -> dict:
    unverified = unverified_numbers(answer, tool_payloads)
    has_numbers = bool(material_numbers(answer))
    if successful_tools == 0 and has_numbers:
        level = "sin_respaldo"
        warning = ("La respuesta contiene cifras pero el asistente NO consultó el Data Warehouse en esta conversación; "
                   "trátelas como no verificadas.")
    elif unverified:
        level = "cifras_no_verificadas"
        warning = ("Las siguientes cifras no aparecen en los datos consultados y no pudieron verificarse: "
                   + ", ".join(unverified) + ". Pueden ser cálculos del modelo o errores; confírmelas en el dashboard.")
    else:
        level = "verificada"
        warning = None
    return {"nivel": level, "cifras_no_verificadas": unverified, "consultas_exitosas": successful_tools,
            "advertencia": warning,
            "nota": "Verificación automática heurística: compara cifras de 4+ dígitos con los datos devueltos por las "
                    "herramientas. No es infalible y no valida afirmaciones cualitativas."}
