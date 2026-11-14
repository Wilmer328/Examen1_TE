# Validación de KPIs y tiempos de respuesta

Generado automáticamente el 2026-11-14 13:49 por `documentation/generar_evidencias.py`.

Cada KPI del servicio analítico (vista `dw.vw_SalesAnalytics`) se compara con una consulta SQL independiente sobre `dw.FactSales` y dimensiones.

| caso | ventas API | ventas SQL | ganancia API | ganancia SQL | facturas API | facturas SQL | coincide | ms servicio |
|---|---|---|---|---|---|---|---|---|
| 2015 completo | 53991490.45 | 53991490.45 | 26957600.65 | 26957600.65 | 22250 | 22250 | True | 964 |
| 2016-Q1 Southeast + Clothing | 549564.0 | 549564.0 | 321143.0 | 321143.0 | 747 | 747 | True | 256 |
| Período sin datos (2030-01) | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | True | 162 |

## Tiempos de respuesta del servicio analítico (sin caché, SQL Server Express local)

| consulta | ms |
|---|---|
| kpis (todo el rango) | 1406 |
| tendencia mensual | 364 |
| ventas por producto top 10 | 2183 |
| detalle página 1 (25 filas) | 485 |
| pronóstico | 12 |
