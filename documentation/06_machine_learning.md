# 6. Machine Learning: pronóstico semanal de ventas por territorio

## Problema, usuario y decisión
- **Problema:** pronosticar las ventas netas (sin impuesto) de cada uno de los 9 territorios de venta para las próximas **1 a 4 semanas** (regresión / serie temporal).
- **Usuario:** gerente comercial regional.
- **Decisión que apoya:** planificar acciones comerciales e inventario por territorio y anticipar caídas (alimenta la alerta R-ALR-02).

## Datos
- Origen: `dw.FactSales` + `DimDate` + `DimGeography` (vía DW, no la fuente).
- Serie: 9 territorios × 178 semanas completas (2013-01-07 → 2016-05-30) = 1 602 observaciones. Semanas sin ventas = 0; la primera semana (parcial) y la semana en curso se excluyen.
- Calidad: sin faltantes tras completar la malla; el territorio *External* tiene volumen bajo y mayor error relativo (sesgo de escala → se modela en escala relativa).

## Variables (sin data leakage)
Origen de predicción `t` = última semana completa. Todas usan información ≤ t:
| Variable | Definición |
|---|---|
| `r_lag_0..3` | ventas de t, t−1, t−2, t−3 divididas por la media móvil de 13 semanas |
| `r_ma_4` | media móvil 4 semanas / media 13 |
| `r_lag52` | ventas de la misma semana del año anterior al **objetivo** (t+h−52 ≤ t) / media 13 |
| `cv_13` | desviación 13 semanas / media 13 |
| `woy_sin, woy_cos` | semana del año del objetivo (calendario, conocido de antemano) |
| `terr_share` | participación del territorio en 13 semanas |
| `SalesTerritory` | one-hot |
Objetivo: `y / media_13`; la predicción se reescala multiplicando por la media 13. La prueba `test_features_use_only_past_information` verifica que ninguna variable use el futuro.

## División temporal (no aleatoria)
| Conjunto | Semanas objetivo | Uso |
|---|---|---|
| Entrenamiento | ≤ 2015-07-05 | ajuste |
| Validación | 2015-07-06 → 2016-01-03 | **selección** de algoritmo/hiperparámetros |
| Prueba | 2016-01-04 → 2016-05-30 (198 filas por horizonte) | evaluación **única**, nunca usada para decidir |

El escalado (`StandardScaler`) se ajusta dentro del `Pipeline` solo con los datos de entrenamiento.

## Líneas base
`naive_ultima_semana` (ŷ = y_t), `naive_estacional_52` (ŷ = y de hace 52 semanas) y `media_movil_4`.

## Selección (validación, h = 1, MAE en USD)
| Candidato | MAE |
|---|---|
| **Ridge(alpha=1)** ✅ | **19 131** |
| HGB(depth=2) | 19 322 |
| Ridge(alpha=10) | 19 259 |
| HGB(depth=3) | 19 912 |
| media_movil_4 | 20 710 |
| naive_ultima_semana | 28 879 |
| naive_estacional_52 | 28 927 |

## Evaluación en prueba (modelo re-entrenado con train+valid)
| Horizonte | MAE modelo | MAE mejor baseline (media móvil 4) | sMAPE modelo | WAPE modelo | Mejora vs mejor baseline |
|---|---|---|---|---|---|
| 1 semana | 22 735 | 24 298 | 23,7 % | 19,5 % | **6,4 %** |
| 2 semanas | 22 932 | 25 239 | 24,0 % | 19,7 % | **9,1 %** |
| 3 semanas | 22 927 | 24 342 | 24,0 % | 19,7 % | **5,8 %** |
| 4 semanas | 22 933 | 24 924 | 24,3 % | 19,7 % | **8,0 %** |
Métricas completas: [evidencias/ml_metricas.json](evidencias/ml_metricas.json) y tabla `ml.ModelRegistry.MetricsJson`.

## Interpretación y limitaciones (honestas)
- El modelo supera a todas las líneas base en todos los horizontes, pero la mejora sobre la media móvil de 4 semanas es **moderada (6–9 %)**: las ventas semanales por territorio son ruidosas (WAPE ≈ 20 %). Es útil para tendencias y alertas, no para cifras exactas.
- La estacionalidad anual aporta poco: solo hay ~3 años; la naive estacional es la peor línea base.
- No incluye promociones, precios ni festivos (no existen en la fuente).
- Las semanas posteriores a 2016-05-31 contienen datos **simulados** (copias del año anterior) y no se usaron en la evaluación.
- Sesgo: territorios pequeños (*External*) tienen mayor error relativo.

## Operación del modelo
- Artefacto: `machine_learning/models/<versión>.joblib` (modelos h=1..4, variables, algoritmo, fecha).
- Registro: `ml.ModelRegistry` (versión, fechas de los conjuntos, variables, parámetros, métricas, ruta, `IsActive`).
- Inferencia: `python -m machine_learning.predict` (también automática tras cada carga ETL) → `ml.Prediction` con versión, fecha de predicción, semana origen y horizonte. API: `GET /api/ml/forecast`.
- Backtest guardado en `ml.BacktestResult` y graficado en el dashboard.
- **Reentrenamiento:** mensual o cuando el MAE móvil de las últimas 8 semanas supere en 20 % el MAE de prueba registrado (monitoreo comparando `ml.Prediction` con hechos reales).
- Extensión: registrar experimentos en MLflow.
