"""Acceso a SQL Server. Todas las consultas con valores externos usan parámetros (?)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

import pandas as pd
import pyodbc

from common import config


def conn_str(database: str, role: str = "etl") -> str:
    base = (f"DRIVER={{{config.ODBC_DRIVER}}};SERVER={config.SQL_SERVER};DATABASE={database};"
            f"Encrypt={config.SQL_ENCRYPT};TrustServerCertificate={config.SQL_TRUST_CERT};")
    if config.SQL_AUTH == "sql":
        user, pwd = ((config.API_DB_USER, config.API_DB_PASSWORD) if role == "api"
                     else (config.ETL_DB_USER, config.ETL_DB_PASSWORD))
        if not pwd:
            raise RuntimeError(f"SQL_AUTH=sql pero falta la contraseña de '{user}' en .env")
        return base + f"UID={user};PWD={pwd};"
    return base + "Trusted_Connection=yes;"


def connect(database: str, role: str = "etl", autocommit: bool = True) -> pyodbc.Connection:
    return pyodbc.connect(conn_str(database, role), autocommit=autocommit, timeout=15)


@contextmanager
def connection(database: str, role: str = "etl", autocommit: bool = True) -> Iterator[pyodbc.Connection]:
    cn = connect(database, role, autocommit)
    try:
        yield cn
    finally:
        cn.close()


def rows_to_df(cursor: pyodbc.Cursor) -> pd.DataFrame:
    cols = [c[0] for c in cursor.description]
    return pd.DataFrame.from_records([tuple(r) for r in cursor.fetchall()], columns=cols)


def query_df(cn: pyodbc.Connection, sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    cur = cn.cursor()
    cur.execute(sql, params or [])
    return rows_to_df(cur)


def query_records(cn: pyodbc.Connection, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
    cur = cn.cursor()
    cur.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def scalar(cn: pyodbc.Connection, sql: str, params: Sequence[Any] | None = None) -> Any:
    cur = cn.cursor()
    cur.execute(sql, params or [])
    row = cur.fetchone()
    return row[0] if row else None


def last_result(cursor: pyodbc.Cursor) -> dict | None:
    """Devuelve el último result set (como dict de la primera fila) de un batch con varios statements."""
    result = None
    while True:
        if cursor.description:
            cols = [c[0] for c in cursor.description]
            row = cursor.fetchone()
            if row is not None:
                result = dict(zip(cols, row))
        if not cursor.nextset():
            break
    return result


def executemany(cn: pyodbc.Connection, sql: str, rows: Iterable[Sequence[Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    cur = cn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    return len(rows)
