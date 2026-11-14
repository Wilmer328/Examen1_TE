# Plataforma Integral de Ingeniería de Datos y Analítica Inteligente — Wide World Importers

Solución de extremo a extremo: **WideWorldImporters (OLTP) → staging (raw / clean / quarantine / ready) → Data Warehouse en estrella → API + dashboard web → pronóstico ML → asistente con IA generativa (Claude) → alertas automáticas**, con auditoría, calidad, reconciliación y monitoreo.

| Capa | Tecnología | Carpeta |
|---|---|---|
| Fuente | SQL Server 2025 Express · WideWorldImporters | `database/` |
| ETL + orquestación | Python 3.14 + SQL (MERGE idempotente), Programador de tareas | `etl/` |
| Staging / DW | `WWI_Staging`, `WWI_DW` (SQL Server) | `database/staging`, `database/data-warehouse` |
| API | FastAPI + JWT | `backend/`, `common/analytics.py` |
| Dashboard | React 18 + Vite + Apache ECharts | `frontend/` |
| ML | scikit-learn (Ridge), división temporal, baselines | `machine_learning/` |
| IA generativa | Claude (`claude-opus-5-5`) con herramientas analíticas limitadas | `generative_ai/` |
| Alertas | Reglas + ML + explicación IA; web (WebSocket) y correo | `notifications/` |
| Pruebas | pytest (31 pruebas) | `tests/` |
| Despliegue | PowerShell; Docker Compose opcional | `deployment/` |

## Requisitos
- Windows 10/11, **SQL Server Express** (instancia `.\SQLEXPRESS`) con `sqlcmd` y **ODBC Driver 18**
- **Python 3.14**, **Node.js 20+**
- (Opcional) API key de Anthropic para el asistente; (opcional) Docker Desktop

## Instalación rápida (≈ 3 minutos)
```powershell
git clone <repo> ; cd <repo>
copy .env.example .env        # complete JWT_SECRET, APP_USERS y ANTHROPIC_API_KEY
powershell -ExecutionPolicy Bypass -File deployment\setup.ps1
powershell -ExecutionPolicy Bypass -File deployment\start.ps1
```
`setup.ps1` crea el entorno Python, instala el frontend, descarga y restaura WideWorldImporters, ejecuta los scripts SQL **en orden**, hace la carga inicial, entrena el modelo, genera predicciones y evalúa alertas. Abra **http://localhost:5173** (API y documentación OpenAPI en http://localhost:8000/docs).

### Paso a paso manual
```powershell
py -3.14 -m venv .venv ; .\.venv\Scripts\pip install -r requirements.txt
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\00_create_databases.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\staging\01_staging_schema.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\data-warehouse\02_dw_schema.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\data-warehouse\03_dw_load_procs.sql
.\.venv\Scripts\python -m etl.pipeline --mode initial      # carga inicial
.\.venv\Scripts\python -m machine_learning.train           # entrena y registra el modelo
.\.venv\Scripts\python -m machine_learning.predict         # predicción batch
.\.venv\Scripts\python -m notifications.alerts             # evalúa alertas
.\.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000
cd frontend ; npm install ; npm run dev
```

## Operación diaria
| Tarea | Comando |
|---|---|
| Carga incremental (+ predicción + alertas) | `python -m etl.pipeline` |
| Programar cada 15 min | `deployment\programar_pipeline.ps1` |
| Simular operaciones nuevas (marcadas SIMULADO) | `python -m etl.simulate_source_changes --days 7 [--territory Southeast --factor 0.4] [--dirty] [--scd2]` |
| Falla controlada (prueba de recuperación) | `python -m etl.pipeline --fail-at load_facts` |
| Alerta de prueba | `python -m notifications.alerts --test` |
| Reintentar notificaciones | `python -m notifications.alerts --retry` |
| Pruebas automatizadas | `python -m pytest -v tests` |
| Regenerar evidencias | `python -m documentation.generar_evidencias` |
| Batería del asistente (usa API) | `python -m generative_ai.eval_assistant` |
| Reiniciar ambiente | `deployment\reset_environment.ps1` |

## Seguridad
- Secretos solo en `.env` (no versionado). `.env.example` no contiene credenciales.
- Cuentas de mínimo privilegio: `deployment\habilitar_sql_auth.ps1 -EtlPassword ... -ApiPassword ...` (como **administrador**) y luego `SQL_AUTH=sql` en `.env`.
- El navegador nunca se conecta a SQL Server; toda consulta es parametrizada; la IA solo usa herramientas de lista blanca.

## Docker (opcional)
```powershell
docker compose -f deployment/docker-compose.yml --env-file .env up -d --build sqlserver
docker compose -f deployment/docker-compose.yml --env-file .env run --rm init
docker compose -f deployment/docker-compose.yml --env-file .env run --rm etl
docker compose -f deployment/docker-compose.yml --env-file .env up -d api frontend   # http://localhost:8080
```
Requiere `MSSQL_SA_PASSWORD`, `ETL_DB_PASSWORD` y `API_DB_PASSWORD` en `.env`. *Nota: los archivos Compose están preparados pero no se probaron en el equipo de desarrollo (Docker no estaba instalado).*

## Documentación
| # | Documento |
|---|---|
| 1 | [Alcance, preguntas analíticas, requerimientos, ERD fuente](documentation/01_alcance_requerimientos.md) |
| 2 | [Arquitectura y decisiones técnicas](documentation/02_arquitectura.md) |
| 3 | [Modelo dimensional, grano, medidas, SCD](documentation/03_modelo_dimensional.md) |
| 4 | [ETL, staging, reglas de calidad, incremental, auditoría](documentation/04_etl_calidad.md) |
| 5 | [KPIs, dashboard y contrato de la API](documentation/05_bi_kpis_api.md) |
| 6 | [Machine Learning](documentation/06_machine_learning.md) |
| 7 | [IA generativa](documentation/07_generative_ai.md) |
| 8 | [Alertas y automatización](documentation/08_alertas_automatizacion.md) |
| 9 | [Seguridad, monitoreo y recuperación](documentation/09_seguridad_operacion.md) |
| 10 | [Plan y resultados de pruebas](documentation/10_plan_pruebas.md) |
| 11 | [Manual de usuario](documentation/11_manual_usuario.md) |
| 12 | [Guion del video y demo](documentation/12_guion_video_demo.md) |
| — | [Evidencias generadas](documentation/evidencias/) (perfil, diccionarios, cargas, KPIs, ML, pytest) |

## Solución de problemas
| Síntoma | Causa / solución |
|---|---|
| `CREATE INDEX failed … QUOTED_IDENTIFIER` | Ejecute `sqlcmd` con `-I` |
| `Data source name not found` | Instale *ODBC Driver 18 for SQL Server* o cambie `ODBC_DRIVER` en `.env` |
| Asistente responde 503 | Falta `ANTHROPIC_API_KEY` en `.env`; reinicie el backend |
| El dashboard muestra 401 | Token expirado: vuelva a iniciar sesión |
