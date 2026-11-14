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

# IA generativa (Claude)
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-opus-5-5")
ASSISTANT_EFFORT = _get("ASSISTANT_EFFORT", "medium")
ASSISTANT_MAX_QUESTION_CHARS = int(_get("ASSISTANT_MAX_QUESTION_CHARS", "500"))
ASSISTANT_RATE_PER_MINUTE = int(_get("ASSISTANT_RATE_PER_MINUTE", "6"))

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
