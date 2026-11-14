# 12. Guion del video (5 min) y de la demo en vivo

## Preparación (antes de grabar)
1. `deployment\start.ps1` (backend + frontend) e iniciar sesión como **admin** en `http://localhost:5173`.
2. Tener una terminal en la raíz con el entorno: `.\.venv\Scripts\activate`.
3. Tener abierto SSMS/Azure Data Studio o una terminal con `sqlcmd` para la consulta de validación.
4. Ocultar el archivo `.env` (no mostrar contraseñas ni la API key).

## Guion con tiempos
| Tiempo | Pantalla | Qué decir / hacer |
|---|---|---|
| 0:00–0:40 | `documentation/02_arquitectura.md` (diagrama) | “Plataforma de datos para ventas de Wide World Importers. Fuente OLTP en SQL Server, staging en 4 zonas, DW en estrella, API FastAPI, dashboard React, pronóstico con scikit-learn, asistente con Claude y alertas. Python + SQL como ETL porque un flujo lineal no justifica Airflow.” |
| 0:40–1:30 | Terminal | `python -m etl.simulate_source_changes --days 7 --territory Southeast --factor 0.4 --dirty` (**decir: es una simulación**) → `python -m etl.pipeline`. Señalar en el log: watermarks, filas extraídas, “rechazadas=2”, reconciliación OK y reglas de calidad. Pestaña *Operación*: clic en la ejecución → pasos; cuarentena con R-IL-01 y R-IL-04. |
| 1:30–2:15 | *Operación* + SQL | Reconciliación fuente = clean + cuarentena = DW. Ejecutar en SQL: `SELECT SUM(NetAmount) FROM WWI_DW.dw.FactSales f JOIN WWI_DW.dw.DimDate d ON d.DateKey=f.DateKey WHERE d.[Year]=2015` y mostrar el SCD2 del cliente 1 (`SELECT * FROM WWI_DW.dw.DimCustomer WHERE CustomerID=1`). |
| 2:15–3:00 | *Dashboard* | Filtrar 2016-01-01 a 2016-03-31; mostrar KPI ventas netas = mismo valor que una consulta SQL (evidencias/05). Cambiar a trimestre; clic en *Southeast* → estados → ciudad; mostrar detalle paginado y “Datos actualizados”. |
| 3:00–3:45 | *Predicciones* | Versión del modelo, tabla modelo vs baselines (mejora 6–9 % frente a media móvil, división temporal, prueba no usada para elegir). Gráfico real vs predicción. Explicar MAE: “error medio absoluto ≈ 22 700 USD por semana y territorio”. |
| 3:45–4:25 | *Asistente IA* | Preguntar “¿Qué categorías tuvieron mayor crecimiento en 2016-Q1 frente a 2015-Q1?” → mostrar etiquetas DATO/INTERPRETACIÓN y Fuentes. Luego “¿Cuántos empleados tiene la empresa en Europa?” → reconoce que no tiene datos. |
| 4:25–5:00 | *Alertas* | Botón *Disparar alerta de prueba* (simulada) → aparece la notificación emergente; abrir detalle: explicación generada por IA, entregas web y correo (`notifications/outbox`). Cierre: “Funciona de extremo a extremo; limitaciones: micro-batch de 15 min, mejora moderada del modelo, cuentas de mínimo privilegio requieren activar autenticación mixta.” |

## Demo en vivo — checklist
- [ ] Explicar cómo iniciar (`deployment\start.ps1`)
- [ ] Ejecutar un lote (`python -m etl.pipeline` o botón *Ejecutar pipeline*)
- [ ] Dashboard + una consulta analítica
- [ ] Predicción con versión identificable (*Predicciones*)
- [ ] Pregunta al asistente
- [ ] Alerta de prueba + registro de entrega
- [ ] Recuperación: `python -m etl.pipeline --fail-at load_facts` → ejecución `failed` en *Operación* → `python -m etl.pipeline` → `success`, sin duplicados
