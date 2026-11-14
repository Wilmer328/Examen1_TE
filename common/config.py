"""Configuración central leída desde variables de entorno (.env). Nunca se versionan secretos."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value if value not in ("",) else default


SQL_SERVER = _get("SQL_SERVER", r".\SQLEXPRESS")
SQL_AUTH = (_get("SQL_AUTH", "windows") or "windows").lower()      # windows | sql
ODBC_DRIVER = _get("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")
SQL_ENCRYPT = _get("SQL_ENCRYPT", "no")
SQL_TRUST_CERT = _get("SQL_TRUST_CERT", "yes")

DB_SOURCE = _get("DB_SOURCE", "WideWorldImporters")
DB_STAGING = _get("DB_STAGING", "WWI_Staging")
DB_DW = _get("DB_DW", "WWI_DW")

# Cuentas técnicas de mínimo privilegio (solo si SQL_AUTH=sql)
ETL_DB_USER = _get("ETL_DB_USER", "etl_user")
ETL_DB_PASSWORD = _get("ETL_DB_PASSWORD")
API_DB_USER = _get("API_DB_USER", "api_user")
API_DB_PASSWORD = _get("API_DB_PASSWORD")

# ETL
EXTRACT_OVERLAP_MINUTES = int(_get("EXTRACT_OVERLAP_MINUTES", "5"))
ETL_MAX_RETRIES = int(_get("ETL_MAX_RETRIES", "3"))
ETL_BATCH_SIZE = int(_get("ETL_BATCH_SIZE", "5000"))

# API / seguridad
JWT_SECRET = _get("JWT_SECRET", "cambiar-este-secreto-en-.env")
JWT_EXPIRE_MINUTES = int(_get("JWT_EXPIRE_MINUTES", "480"))
APP_USERS = _get("APP_USERS", "analista:analista123:analyst,admin:admin123:admin")  # usuario:clave:rol
CORS_ORIGINS = [o.strip() for o in (_get("CORS_ORIGINS", "http://localhost:5173") or "").split(",") if o.strip()]

# IA generativa: proveedor intercambiable (ollama = local, por defecto | anthropic = Claude en la nube)
LLM_PROVIDER = (_get("LLM_PROVIDER", "ollama") or "ollama").lower()
# Ollama (local). Límites pensados para un equipo de ~8 GB de RAM.
OLLAMA_BASE_URL = (_get("OLLAMA_BASE_URL", "http://localhost:11434") or "").rstrip("/")
OLLAMA_MODEL = _get("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_NUM_CTX = int(_get("OLLAMA_NUM_CTX", "8192"))          # ventana de contexto (tokens); determina la RAM de la caché KV
OLLAMA_NUM_PREDICT = int(_get("OLLAMA_NUM_PREDICT", "768"))   # máximo de tokens generados por turno
OLLAMA_TIMEOUT = float(_get("OLLAMA_TIMEOUT", "300"))          # segundos por llamada al modelo (CPU: puede ser lento)
OLLAMA_KEEP_ALIVE = _get("OLLAMA_KEEP_ALIVE", "5m")             # tiempo que el modelo queda en memoria tras usarse
# json   = planificación con salida JSON restringida (recomendado para modelos pequeños como qwen2.5:1.5b)
# native = llamadas a herramientas nativas de Ollama (mejor con modelos de 7B o más)
OLLAMA_TOOL_MODE = (_get("OLLAMA_TOOL_MODE", "json") or "json").lower()
# Anthropic (alternativa)
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-opus-5-5")
ASSISTANT_EFFORT = _get("ASSISTANT_EFFORT", "medium")
# Comunes
ASSISTANT_MAX_QUESTION_CHARS = int(_get("ASSISTANT_MAX_QUESTION_CHARS", "500"))
ASSISTANT_RATE_PER_MINUTE = int(_get("ASSISTANT_RATE_PER_MINUTE", "6"))
ASSISTANT_MAX_TURNS = int(_get("ASSISTANT_MAX_TURNS", "5"))
ASSISTANT_TOOL_RESULT_MAX_CHARS = int(_get("ASSISTANT_TOOL_RESULT_MAX_CHARS", "6000"))

# Notificaciones
SMTP_HOST = _get("SMTP_HOST")
SMTP_PORT = int(_get("SMTP_PORT", "587"))
SMTP_USER = _get("SMTP_USER")
SMTP_PASSWORD = _get("SMTP_PASSWORD")
SMTP_FROM = _get("SMTP_FROM", "alertas@plataforma.local")
ALERT_EMAIL_TO = _get("ALERT_EMAIL_TO", "analista@plataforma.local")
ALERT_DROP_THRESHOLD = float(_get("ALERT_DROP_THRESHOLD", "0.15"))     # caída > 15 %
ALERT_ML_THRESHOLD = float(_get("ALERT_ML_THRESHOLD", "0.80"))         # predicción < 80 % del promedio

OUTBOX_DIR = ROOT / "notifications" / "outbox"
MODELS_DIR = ROOT / "machine_learning" / "models"
EVIDENCE_DIR = ROOT / "documentation" / "evidencias"
