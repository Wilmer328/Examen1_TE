# 5. Business Intelligence: KPIs, dashboard y API

## Catálogo de KPIs
Fuente de todos: `dw.vw_SalesAnalytics` (FactSales + dimensiones, grano línea de factura). Responsable: analista comercial (rol `analyst`). Filtros aplicables: rango de fechas, territorio, categoría de producto, categoría de cliente, grupo de compra (+ estado, cliente, producto por drill-down). Cada KPI se compara contra el período anterior de igual duración.

| KPI | Propósito | Fórmula | Unidad | Granularidad |
|---|---|---|---|---|
| Ventas netas | Volumen facturado sin impuesto | `Σ NetAmount` (= Σ Quantity × UnitPrice) | USD | línea → cualquier agregado |
| Ganancia | Rentabilidad absoluta | `Σ LineProfit` | USD | ídem |
| Margen % | Rentabilidad relativa | `Σ LineProfit / Σ NetAmount × 100` (no aditivo) | % (variación en puntos porcentuales) | se recalcula por agregado |
| Facturas | Actividad comercial | `COUNT(DISTINCT InvoiceID)` | facturas | ídem |
| Ticket promedio | Tamaño de compra | `Σ NetAmount / COUNT(DISTINCT InvoiceID)` | USD/factura | ídem |
| Clientes activos | Amplitud de la base | `COUNT(DISTINCT CustomerID)` | clientes | ídem |

> Ventas netas = importe bruto − impuesto. WWI no tiene descuentos por línea ni devoluciones (no hay notas de crédito), por lo que no se restan.

## Validación
| Prueba | Resultado |
|---|---|
| KPI vs SQL independiente (2015, 2016-Q1 con filtros combinados, período sin datos) | Coinciden al centavo — [evidencias/05_validacion_kpis.md](evidencias/05_validacion_kpis.md) |
| Suma por territorio = total (no se duplica por joins) | `test_breakdown_totals_not_duplicated_by_joins` |
| Período sin datos | Devuelve 0 y la interfaz muestra “Sin datos para los filtros seleccionados” |
| Credenciales no expuestas | `test_freshness_and_no_credentials_exposed`; el navegador solo conoce un JWT |
| Tiempos de respuesta | 0,1–2,2 s por consulta principal en SQL Express local (tabla en evidencias) |

## Funcionalidades del dashboard (checklist de la guía)
| Requisito | Dónde |
|---|---|
| Autenticación | Login JWT (usuarios en `.env`, roles analyst/admin) |
| 4–6 KPIs | 6 tarjetas con variación vs período anterior |
| Filtros por fecha + ≥ 2 dimensiones | Fecha desde/hasta, territorio, categoría producto, categoría cliente, grupo de compra |
| Tendencias y comparación | Línea por año/trimestre/mes/semana; variación % de cada KPI |
| Visualización por categoría/producto/cliente/región | Barras por 9 dimensiones |
| Tabla de detalle paginada | 15 filas por página, máx. 200 por API |
| Drill-down | Clic en barra: territorio → estado → ciudad; categoría → producto; categoría cliente → cliente |
| Fecha/hora de última actualización | Cabecera (“Datos actualizados …”) |
| Estados de carga / error / sin datos | Componente `Status` en cada panel |
| Escritorio y móvil | CSS responsive |
| Predicción identificada | Pestaña *Predicciones* con insignia “PREDICCIÓN · no es dato histórico” |

## Contrato de la API (resumen; documentación interactiva en `http://localhost:8000/docs`)
Todas requieren `Authorization: Bearer <token>` salvo login y health. Errores de validación → 422; sin permisos → 403.

| Método y ruta | Parámetros | Respuesta |
|---|---|---|
| `POST /api/auth/login` | form `username`, `password` | `{access_token, user{username, role}}` |
| `GET /api/meta/filters` | — | valores para filtros + rango de fechas |
| `GET /api/meta/freshness` | — | última carga exitosa y rango de datos |
| `GET /api/kpis` | `start, end, territorio, categoria, categoria_cliente, grupo_compra, estado, cliente, producto` | `{periodo, periodo_anterior, actual{…}, anterior{…}, variacion_pct{…}, fuente}` |
| `GET /api/sales/trend` | filtros + `grain=anio|trimestre|mes|semana` | `[{periodo, ventas_netas, ganancia, facturas}]` |
| `GET /api/sales/by` | filtros + `dimension` (lista blanca) + `top_n≤50` | `[{miembro, ventas_netas, ganancia, unidades, facturas, participacion_pct}]` |
| `GET /api/sales/compare` | `dimension, actual_inicio, actual_fin, anterior_inicio, anterior_fin` | `[{miembro, actual, anterior, variacion_pct}]` |
| `GET /api/sales/detail` | filtros + `page, page_size≤200` | `{total, page, page_size, rows[]}` |
| `GET /api/ml/forecast` · `/api/ml/models` · `/api/ml/backtest` | `territorio` | predicciones con versión; registro de modelos y métricas; real vs predicho |
| `POST /api/ml/predict` *(admin)* | — | ejecuta inferencia batch |
| `POST /api/assistant/ask` | JSON `{pregunta ≤ 500}` | `{respuesta, herramientas_usadas[], modelo, tokens, datos_actualizados, aviso}` |
| `GET /api/alerts` · `PATCH /api/alerts/{id}` · `GET /api/alerts/{id}/deliveries` | `estado` / `{status}` | alertas, cambio de estado, entregas |
| `POST /api/alerts/evaluate` · `/api/alerts/test` *(admin)* | — | evaluación de reglas / alerta de prueba simulada |
| `WS /ws/alerts?token=` | — | mensajes `{tipo:"alerta_nueva", …}` |
| `GET /api/ops/summary` · `/api/ops/runs/{id}` · `POST /api/ops/run-pipeline` *(admin)* | — | monitoreo operativo |
| `GET /api/health` | — | estado de la API y la base |

**Contrato de datos:** las fechas viajan como ISO `YYYY-MM-DD`; los montos como número decimal en USD sin impuesto (salvo `GrossAmount`); dimensiones y granularidades solo de lista blanca (`common/analytics.py: DIMENSIONS, GRAINS`).
