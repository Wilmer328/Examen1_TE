"""Entrenamiento y evaluación del pronóstico semanal de ventas por territorio.

Flujo: DW -> serie semanal -> variables -> división TEMPORAL (train / validación / prueba)
-> líneas base -> selección de modelo en VALIDACIÓN -> re-entrenamiento train+valid -> evaluación
UNA sola vez en PRUEBA -> registro (ml.ModelRegistry) + backtest (ml.BacktestResult) + artefacto .joblib.

Uso:  python -m machine_learning.train
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import config, db
from machine_learning.features import HORIZONS, load_weekly, make_supervised

log = logging.getLogger("ml")

TRAIN_END = pd.Timestamp("2015-07-05")     # objetivo <= esta fecha -> entrenamiento
VALID_END = pd.Timestamp("2016-01-03")     # (TRAIN_END, VALID_END] -> validación ; > VALID_END -> prueba
REL_FEATURES = ["r_lag_0", "r_lag_1", "r_lag_2", "r_lag_3", "r_ma_4", "r_lag52", "cv_13", "woy_sin", "woy_cos", "terr_share"]


def to_relative(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza por la media móvil de 13 semanas para que un solo modelo sirva a territorios de escala distinta."""
    out = df.copy()
    base = out["ma_13"].where(out["ma_13"] > 1.0, 1.0)
    out["_base"] = base
    for k in range(4):
        out[f"r_lag_{k}"] = out[f"lag_{k}"] / base
    out["r_ma_4"] = out["ma_4"] / base
    out["r_lag52"] = out["lag52_target"] / base
    out["cv_13"] = out["std_13"] / base
    if "y" in out:
        out["y_rel"] = out["y"] / base
    return out


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    nz = y != 0
    return {
        "MAE": float(np.mean(np.abs(y - p))),
        "RMSE": float(np.sqrt(np.mean((y - p) ** 2))),
        "MAPE_%": float(np.mean(np.abs((y[nz] - p[nz]) / y[nz])) * 100) if nz.any() else None,
        "sMAPE_%": float(np.mean(2 * np.abs(y - p) / np.maximum(np.abs(y) + np.abs(p), 1e-9)) * 100),
        "WAPE_%": float(np.sum(np.abs(y - p)) / max(np.sum(np.abs(y)), 1e-9) * 100),
        "n": int(len(y)),
    }


def baselines(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {"naive_ultima_semana": df["lag_0"].to_numpy(),
            "naive_estacional_52": df["lag52_target"].to_numpy(),
            "media_movil_4": df["ma_4"].to_numpy()}


def candidates() -> dict:
    pre = ColumnTransformer([("num", StandardScaler(), REL_FEATURES),
                             ("terr", OneHotEncoder(handle_unknown="ignore"), ["SalesTerritory"])])
    return {
        "Ridge(alpha=1)": Pipeline([("pre", pre), ("m", Ridge(alpha=1.0))]),
        "Ridge(alpha=10)": Pipeline([("pre", pre), ("m", Ridge(alpha=10.0))]),
        "HGB(depth=3,lr=0.05,it=300)": Pipeline([("pre", pre), ("m", HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0, random_state=42))]),
        "HGB(depth=2,lr=0.03,it=200)": Pipeline([("pre", pre), ("m", HistGradientBoostingRegressor(
            max_depth=2, learning_rate=0.03, max_iter=200, l2_regularization=1.0, random_state=42))]),
    }


def split(df: pd.DataFrame):
    tr = df[df["target_week"] <= TRAIN_END]
    va = df[(df["target_week"] > TRAIN_END) & (df["target_week"] <= VALID_END)]
    te = df[df["target_week"] > VALID_END]
    return tr, va, te


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    weekly, last_complete = load_weekly()
    log.info("Serie semanal: %s filas, %s territorios, %s -> %s", len(weekly), weekly.SalesTerritory.nunique(),
             weekly.WeekStart.min().date(), last_complete.date())

    version = f"wwi-weekly-v{datetime.now():%Y%m%d%H%M}"
    report: dict = {"version": version, "problem": "Pronóstico semanal de ventas netas por territorio (h=1..4 semanas)",
                    "split": {"train_end": str(TRAIN_END.date()), "valid_end": str(VALID_END.date()),
                              "test_end": str(last_complete.date())}, "horizons": {}}
    final_models: dict[int, Pipeline] = {}
    chosen_name = None
    backtest = None

    # 1) Selección de algoritmo con h=1 usando SOLO validación
    sup1 = to_relative(make_supervised(weekly, 1))
    tr, va, te = split(sup1)
    val_scores = {}
    for name, model in candidates().items():
        model.fit(tr[REL_FEATURES + ["SalesTerritory"]], tr["y_rel"])
        pred = model.predict(va[REL_FEATURES + ["SalesTerritory"]]) * va["_base"]
        val_scores[name] = metrics(va["y"], pred)
    for name, pred in baselines(va).items():
        val_scores[name] = metrics(va["y"], pred)
    chosen_name = min((k for k in val_scores if k in candidates()), key=lambda k: val_scores[k]["MAE"])
    report["validation_h1"] = val_scores
    report["selected_algorithm"] = chosen_name
    log.info("Validación h=1 (MAE): %s", {k: round(v["MAE"]) for k, v in val_scores.items()})
    log.info("Algoritmo seleccionado: %s", chosen_name)

    # 2) Para cada horizonte: re-entrenar en train+valid y evaluar UNA vez en prueba
    for h in HORIZONS:
        sup = to_relative(make_supervised(weekly, h))
        tr, va, te = split(sup)
        trva = pd.concat([tr, va])
        model = candidates()[chosen_name]
        model.fit(trva[REL_FEATURES + ["SalesTerritory"]], trva["y_rel"])
        pred = np.clip(model.predict(te[REL_FEATURES + ["SalesTerritory"]]) * te["_base"], 0, None)
        res = {"model": metrics(te["y"], pred)}
        res.update({k: metrics(te["y"], v) for k, v in baselines(te).items()})
        best_base = min((k for k in res if k != "model"), key=lambda k: res[k]["MAE"])
        res["best_baseline"] = best_base
        res["improvement_vs_best_baseline_%"] = round((1 - res["model"]["MAE"] / res[best_base]["MAE"]) * 100, 2)
        res["train_rows"], res["test_rows"] = int(len(trva)), int(len(te))
        report["horizons"][h] = res
        final_models[h] = model
        log.info("h=%s prueba MAE modelo=%.0f | mejor baseline %s=%.0f | mejora %.1f%%", h, res["model"]["MAE"],
                 best_base, res[best_base]["MAE"], res["improvement_vs_best_baseline_%"])
        if h == 1:
            backtest = te.assign(pred=pred, base=te["lag52_target"].fillna(te["lag_0"]))

    # 3) Re-entrenamiento final con TODOS los datos etiquetados para producción (mismo algoritmo/hiperparámetros)
    for h in HORIZONS:
        sup = to_relative(make_supervised(weekly, h))
        m = candidates()[chosen_name]
        m.fit(sup[REL_FEATURES + ["SalesTerritory"]], sup["y_rel"])
        final_models[h] = m

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = config.MODELS_DIR / f"{version}.joblib"
    joblib.dump({"version": version, "algorithm": chosen_name, "models": final_models, "features": REL_FEATURES,
                 "trained_at": datetime.now().isoformat(), "last_complete_week": str(last_complete.date())}, artifact)

    weeks_te = backtest["target_week"]
    with db.connection(config.DB_DW) as cn:
        cur = cn.cursor()
        cur.execute("UPDATE ml.ModelRegistry SET IsActive = 0")
        cur.execute(
            "INSERT ml.ModelRegistry (ModelVersion, ModelName, Algorithm, TrainStart, TrainEnd, ValidStart, ValidEnd, TestStart,"
            " TestEnd, FeaturesJson, ParamsJson, MetricsJson, ArtifactPath, IsActive) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            version, "Pronóstico semanal de ventas netas por territorio", chosen_name,
            weekly.WeekStart.min().date(), TRAIN_END.date(), (TRAIN_END + pd.Timedelta(days=1)).date(), VALID_END.date(),
            weeks_te.min().date(), weeks_te.max().date(), json.dumps(REL_FEATURES + ["SalesTerritory"]),
            json.dumps({"selected": chosen_name, "target": "y / media_movil_13", "horizons": HORIZONS}),
            json.dumps(report, default=str), str(artifact.relative_to(config.ROOT)))
        db.executemany(cn, "INSERT ml.BacktestResult (ModelVersion, SalesTerritory, WeekStart, SplitName, ActualNetAmount,"
                           " PredictedNetAmount, BaselineNetAmount) VALUES (?,?,?,?,?,?,?)",
                       [(version, r.SalesTerritory, r.target_week.date(), "test", round(r.y, 2), round(r.pred, 2),
                         round(r.base, 2)) for r in backtest.itertuples()])

    config.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (config.EVIDENCE_DIR / "ml_metricas.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"MODEL_VERSION={version}")


if __name__ == "__main__":
    main()
