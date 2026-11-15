# 10. Plan y resultados de pruebas

Ejecución: `python -m pytest -v tests` → **47 pruebas, 47 aprobadas** (31 originales + 16 de integración con Ollama; salida completa: [evidencias/07_resultados_pytest.txt](evidencias/07_resultados_pytest.txt)). Requiere la base cargada; las pruebas de pipeline ejecutan cargas reales.

## Matriz (pruebas de la guía → evidencia)
| Prueba de la guía | Qué se demuestra | Prueba automatizada / evidencia | Resultado |
|---|---|---|---|
| Carga inicial | 12 objetos extraídos y cargados; conteos registrados | Ejecución 1 en `ops.EtlStepLog` ([04_resultados_carga](evidencias/04_resultados_carga.md)) — 228 265 líneas en ≈ 40 s | ✅ |
| Carga incremental | Solo cambios (watermark + solapamiento); 7 días simulados = 1 617 líneas nuevas, 496 facturas, 1 cliente SCD2 | Ejecución incremental con cambios en evidencias | ✅ |
| Idempotencia | Re-ejecutar no inserta ni actualiza | `test_incremental_is_idempotent` | ✅ |
| Nulos y duplicados | Precio nulo derivado y marcado; espacios limpiados; supervivencia por watermark | `test_quarantine_and_derivation_rules_applied`, `test_catalog_has_rules_and_keys` | ✅ |
| Integridad | Huérfanos → cuarentena con reintento; miembros −1 = 0 | `test_no_duplicate_grain_and_no_unknown_members`, regla R-IL-05 | ✅ |
| Recuperación | Falla controlada en `load_facts` → `failed`, watermarks intactos, reintento exitoso sin cambios en el DW | `test_controlled_failure_does_not_advance_watermark_and_recovers` | ✅ |
| Reconciliación | fuente = clean + cuarentena; clean = DW (filas y monto) | `test_reconciliation_between_layers`, `test_fact_total_matches_source_minus_quarantine` | ✅ |
| SCD2 | Una versión vigente; sin solapes | `test_scd2_single_current_version_and_non_overlapping` | ✅ |
| Dashboard | KPIs = SQL independiente (sin filtros, filtros combinados, período vacío); totales no duplicados; paginación; validación de entradas | `test_api_bi.py` (10 pruebas) + [05_validacion_kpis](evidencias/05_validacion_kpis.md) | ✅ |
| Seguridad API | 401 sin token / token falso / clave errónea; 403 analista en endpoint admin; sin credenciales en respuestas | `test_requires_authentication`, `test_wrong_password_rejected`, `test_admin_endpoints_forbidden_for_analyst`, `test_freshness_and_no_credentials_exposed` | ✅ |
| ML | Sin leakage; división temporal sin solapes; baseline registrado; evaluación en prueba | `test_features_use_only_past_information`, `test_temporal_split_has_no_overlap`, `test_active_model_registered_with_baseline_comparison` | ✅ |
| GenAI | Herramientas fuera de lista blanca rechazadas; parámetros inválidos rechazados; herramientas devuelven datos del DW; límite de tamaño; 503 sin credencial | 5 pruebas en `test_ml_alerts_genai.py` + 16 en `test_ollama_integration.py` (Ollama simulado y real: herramientas generadas desde la lista única, todo pasa por `run_tool`, herramienta inexistente rechazada, Ollama caído → 503, timeout, modelo no descargado, registro de fallas, verificación de cifras) + batería de 12 preguntas contra `qwen2.5:1.5b` real | ✅ integración y seguridad / ⚠️ calidad: 10/12 automático, **5 correctas · 3 parciales · 4 fallidas** en revisión manual ([06_pruebas_asistente](evidencias/06_pruebas_asistente.md)) |
| Alertas | Disparo (> 15 %), no disparo (= 15 %), regla ML, deduplicación, registro de entrega web+correo | 5 pruebas en `test_ml_alerts_genai.py` + outbox | ✅ |
| End-to-end | Fuente → staging → DW → API → dashboard → ML → alerta | Demo en vivo y ejecución de `etl.pipeline` con post-pasos | ✅ |

## Hallazgo durante las pruebas (y corrección)
- **Espera de memoria en SQL Express (`RESOURCE_SEMAPHORE`)**: el cálculo del umbral de outliers ordenaba toda la tabla `raw.InvoiceLines` en cada carga y, junto con consultas concurrentes, dejaba sesiones esperando memoria varios minutos. Corrección: el umbral se calcula una sola vez y se persiste en `clean.QualityParameter`; la selección del lote se reescribió con `UNION ALL` + `CROSS APPLY` indexado. Resultado: incremental de ≈ 7 s y suite completa en 26 s.
- **Cuarentena duplicada**: un registro que volvía a fallar la misma regla se insertaba otra vez en cada carga. Corrección: no se re-inserta si ya existe pendiente con la misma regla.
- **Límite exacto del umbral**: 1 − 85/100 = 0,15000000000000002 disparaba la alerta con umbral 15 %. Corrección: redondeo a 6 decimales (prueba de no-disparo).
