"""Mantiene "calientes" SQL Server y Ollama para que el sitio responda rápido siempre.

Problema medido (equipo de 7,7 GB de RAM con ~0,8 GB libres): tras unos minutos sin uso, Windows
saca de la RAM las páginas de SQL Server y del modelo de Ollama. La primera consulta vuelve a leerlas
del disco: /api/kpis tardó 83 s en frío y 0,3 s en caliente; el túnel ngrok solo agrega ~0,1-0,3 s.

Este script repite cada INTERVALO segundos las consultas que hace el dashboard al abrirse
(a través de la API local, con las mismas validaciones) y un "ping" mínimo a Ollama con el mismo
num_ctx que usa el asistente, para que el modelo no se recargue. No modifica datos.

Uso:  .venv\\Scripts\\python.exe -m deployment.keep_warm            (Ctrl+C para detener)
      .venv\\Scripts\\python.exe -m deployment.keep_warm --intervalo 120
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime

import httpx

from common import config

API = "http://127.0.0.1:8000/api"
# Mismos parámetros iniciales que frontend/src/pages/Dashboard.jsx
DASH = {"start": "2016-01-01", "end": "2016-06-07"}
RUTAS = [
    ("/meta/freshness", {}),
    ("/meta/filters", {}),
    ("/kpis", DASH),
    ("/sales/trend", {**DASH, "grain": "mes"}),
    ("/sales/by", {**DASH, "dimension": "territorio", "top_n": 12}),
    ("/sales/detail", {**DASH, "page": 1, "page_size": 15}),
    ("/ml/forecast", {}),
    ("/ml/models", {}),
    ("/alerts", {"limit": 100}),
    ("/ops/summary", {}),
]


def _credenciales() -> tuple[str, str]:
    # Usa la cuenta de analista del .env (solo lectura); nunca imprime la clave.
    usuarios = [u.split(":") for u in config.APP_USERS.split(",") if u.count(":") == 2]
    for nombre, clave, rol in usuarios:
        if rol == "analyst":
            return nombre, clave
    nombre, clave, _ = usuarios[0]
    return nombre, clave


def calentar_api(cliente: httpx.Client, token: str | None) -> tuple[str | None, list[str]]:
    if token is None:
        u, p = _credenciales()
        r = cliente.post(f"{API}/auth/login", data={"username": u, "password": p})
        r.raise_for_status()
        token = r.json()["access_token"]
    marcas = []
    for ruta, params in RUTAS:
        t = time.perf_counter()
        r = cliente.get(f"{API}{ruta}", params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 401:  # token vencido: se renueva en la siguiente vuelta
            return None, marcas + [f"{ruta} 401"]
        marcas.append(f"{ruta.split('/')[-1]} {time.perf_counter() - t:.1f}s")
    return token, marcas


def calentar_ollama(cliente: httpx.Client) -> str:
    if config.LLM_PROVIDER != "ollama":
        return "ollama omitido"
    t = time.perf_counter()
    r = cliente.post(f"{config.OLLAMA_BASE_URL}/api/generate", json={
        "model": config.OLLAMA_MODEL, "prompt": "ok", "stream": False,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,
        # num_ctx igual al del asistente: si difiere, Ollama recarga el modelo en la siguiente pregunta
        "options": {"num_ctx": config.OLLAMA_NUM_CTX, "num_predict": 1, "temperature": 0},
    })
    r.raise_for_status()
    return f"ollama {time.perf_counter() - t:.1f}s"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--intervalo", type=int, default=120, help="segundos entre vueltas (predeterminado 120)")
    args = ap.parse_args()
    print(f"Manteniendo caliente la API y Ollama cada {args.intervalo} s. Ctrl+C para detener.")
    token = None
    with httpx.Client(timeout=300) as cliente:
        while True:
            hora = datetime.now().strftime("%H:%M:%S")
            try:
                token, marcas = calentar_api(cliente, token)
                marcas.append(calentar_ollama(cliente))
                print(hora, " | ".join(marcas), flush=True)
            except Exception as e:  # el backend u Ollama pueden estar apagados: se reintenta en la siguiente vuelta
                print(hora, "aviso:", type(e).__name__, str(e)[:150], flush=True)
            time.sleep(args.intervalo)


if __name__ == "__main__":
    main()
