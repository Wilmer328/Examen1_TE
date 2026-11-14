"""Inferencia batch con el modelo ACTIVO: pronóstico h=1..4 semanas desde la última semana completa.
Guarda en ml.Prediction con versión del modelo, fecha de predicción, semana origen y horizonte.

Uso:  python -m machine_learning.predict
"""
from __future__ import annotations

import logging

import joblib
import numpy as np
import pandas as pd

from common import config, db
from machine_learning.features import HORIZONS, load_weekly, make_supervised
from machine_learning.train import to_relative

log = logging.getLogger("ml")


def load_active_model() -> dict:
    with db.connection(config.DB_DW) as cn:
        row = db.query_records(cn, "SELECT TOP 1 ModelVersion, ArtifactPath FROM ml.ModelRegistry WHERE IsActive = 1")
    if not row:
        raise FileNotFoundError("No hay modelo activo en ml.ModelRegistry")
    path = config.ROOT / row[0]["ArtifactPath"]
    if not path.exists():
        raise FileNotFoundError(f"No existe el artefacto {path}")
    return joblib.load(path)


def forecast(bundle: dict | None = None) -> pd.DataFrame:
    bundle = bundle or load_active_model()
    weekly, last_complete = load_weekly()
    rows = []
    for h in HORIZONS:
        sup = to_relative(make_supervised(weekly, h, include_unlabeled=True))
        origin = sup[sup["origin_week"] == last_complete]
        pred = np.clip(bundle["models"][h].predict(origin[bundle["features"] + ["SalesTerritory"]]) * origin["_base"], 0, None)
        rows.append(pd.DataFrame({"SalesTerritory": origin["SalesTerritory"].to_numpy(), "AsOfWeek": last_complete.date(),
                                  "TargetWeekStart": origin["target_week"].dt.date.to_numpy(), "HorizonWeeks": h,
                                  "PredictedNetAmount": np.round(pred, 2)}))
    out = pd.concat(rows, ignore_index=True)
    out["ModelVersion"] = bundle["version"]
    return out


def run_batch_prediction() -> pd.DataFrame:
    bundle = load_active_model()
    out = forecast(bundle)
    with db.connection(config.DB_DW) as cn:
        cur = cn.cursor()
        for r in out.itertuples():
            cur.execute(
                "MERGE ml.Prediction AS t USING (SELECT ? v, ? terr, ? asof, ? tw) s"
                " ON t.ModelVersion = s.v AND t.SalesTerritory = s.terr AND t.AsOfWeek = s.asof AND t.TargetWeekStart = s.tw"
                " WHEN MATCHED THEN UPDATE SET PredictedNetAmount = ?, PredictionDate = SYSDATETIME()"
                " WHEN NOT MATCHED THEN INSERT (ModelVersion, SalesTerritory, AsOfWeek, TargetWeekStart, HorizonWeeks, PredictedNetAmount)"
                "   VALUES (s.v, s.terr, s.asof, s.tw, ?, ?);",
                r.ModelVersion, r.SalesTerritory, r.AsOfWeek, r.TargetWeekStart, float(r.PredictedNetAmount),
                int(r.HorizonWeeks), float(r.PredictedNetAmount))
    log.info("Predicciones guardadas: %s filas (modelo %s, origen %s)", len(out), bundle["version"], out.AsOfWeek.iloc[0])
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(run_batch_prediction().to_string(index=False))
