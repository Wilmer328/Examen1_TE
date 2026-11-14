"""Construcción reproducible de la serie semanal y de variables (feature engineering) SIN data leakage.

Problema: pronosticar las ventas netas (sin impuesto) de las próximas h semanas (h = 1..4) por
territorio de venta. Origen de predicción = última semana COMPLETA conocida (t). Todas las variables
usan solo información <= t (lags, medias móviles) o atributos de calendario del objetivo (conocidos de
antemano). lag52 del objetivo es t+h-52 <= t para h <= 4, por lo que también es conocido.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import config, db

HORIZONS = [1, 2, 3, 4]
FEATURES = ["lag_0", "lag_1", "lag_2", "lag_3", "ma_4", "ma_13", "std_13", "lag52_target",
            "woy_sin", "woy_cos", "terr_share"]

WEEKLY_SQL = """
SELECT g.SalesTerritory, d.WeekStart, SUM(f.NetAmount) AS NetAmount
FROM dw.FactSales f
JOIN dw.DimDate d ON d.DateKey = f.DateKey
JOIN dw.DimGeography g ON g.GeographyKey = f.GeographyKey
WHERE g.SalesTerritory <> 'Desconocido'
GROUP BY g.SalesTerritory, d.WeekStart
"""


def load_weekly(cn=None) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Devuelve la serie semanal completa (territorio x semana, semanas sin ventas = 0) y la última semana completa."""
    own = cn is None
    cn = cn or db.connect(config.DB_DW)
    try:
        df = db.query_df(cn, WEEKLY_SQL)
        max_date = pd.Timestamp(db.scalar(cn, "SELECT MAX(d.[Date]) FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey"))
    finally:
        if own:
            cn.close()
    df["WeekStart"] = pd.to_datetime(df["WeekStart"])
    df["NetAmount"] = df["NetAmount"].astype(float)
    # Semana completa: termina (domingo) en o antes de la última fecha con datos
    last_complete = (max_date - pd.Timedelta(days=max_date.dayofweek)) - pd.Timedelta(days=7 if max_date.dayofweek < 6 else 0)
    first_full = df["WeekStart"].min() + pd.Timedelta(days=7)   # la primera semana (2013-01-01 es martes) es parcial
    weeks = pd.date_range(first_full, last_complete, freq="W-MON")
    full = (pd.MultiIndex.from_product([sorted(df["SalesTerritory"].unique()), weeks], names=["SalesTerritory", "WeekStart"])
            .to_frame(index=False)
            .merge(df, how="left", on=["SalesTerritory", "WeekStart"]))
    full["NetAmount"] = full["NetAmount"].fillna(0.0)
    return full.sort_values(["SalesTerritory", "WeekStart"]).reset_index(drop=True), last_complete


def _territory_features(s: pd.Series, total: pd.Series) -> pd.DataFrame:
    f = pd.DataFrame(index=s.index)
    for k in range(4):
        f[f"lag_{k}"] = s.shift(k)                     # lag_0 = semana origen t
    f["ma_4"] = s.rolling(4).mean()
    f["ma_13"] = s.rolling(13).mean()
    f["std_13"] = s.rolling(13).std()
    f["terr_share"] = (s.rolling(13).sum() / total.rolling(13).sum()).fillna(0)
    return f


def make_supervised(weekly: pd.DataFrame, horizon: int, include_unlabeled: bool = False) -> pd.DataFrame:
    """Una fila por (territorio, semana origen t) con objetivo y = ventas de t + horizon."""
    total = weekly.groupby("WeekStart")["NetAmount"].sum()
    out = []
    for terr, g in weekly.groupby("SalesTerritory"):
        g = g.set_index("WeekStart")["NetAmount"]
        f = _territory_features(g, total.reindex(g.index))
        f["SalesTerritory"] = terr
        f["origin_week"] = g.index
        f["target_week"] = g.index + pd.Timedelta(weeks=horizon)
        f["y"] = g.shift(-horizon)
        f["lag52_target"] = g.shift(52 - horizon)      # valor de la misma semana del año anterior al objetivo
        woy = f["target_week"].dt.isocalendar().week.astype(float)
        f["woy_sin"] = np.sin(2 * np.pi * woy / 52.0)
        f["woy_cos"] = np.cos(2 * np.pi * woy / 52.0)
        f["horizon"] = horizon
        out.append(f.reset_index(drop=True))
    df = pd.concat(out, ignore_index=True)
    df = df.dropna(subset=[c for c in FEATURES])
    if not include_unlabeled:
        df = df.dropna(subset=["y"])
    return df
