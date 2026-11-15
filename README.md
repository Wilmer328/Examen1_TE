# Plataforma Integral de Ingeniería de Datos y Analítica Inteligente — Wide World Importers

Solución de extremo a extremo: **WideWorldImporters (OLTP) → staging (raw / clean / quarantine / ready) → Data Warehouse en estrella → API + dashboard web → pronóstico ML → asistente con IA generativa (Ollama local o Claude) → alertas automáticas**, con auditoría, calidad, reconciliación y monitoreo.

| Capa | Tecnología | Carpeta |
|---|---|---|
| Fuente | SQL Server 2025 Express · WideWorldImporters | `database/` |
| ETL + orquestación | Python 3.14 + SQL (MERGE idempotente), Programador de tareas | `etl/` |
| Staging / DW | `WWI_Staging`, `WWI_DW` (SQL Server) | `database/staging`, `database/data-warehouse` |
| API | FastAPI + JWT | `backend/`, `common/analytics.py` |
| Dashboard | React 18 + Vite + Apache ECharts | `frontend/` |
| ML | scikit-learn (Ridge), división temporal, baselines | `machine_learning/` |
| IA generativa | **Ollama local** (`qwen2.5:1.5b`, predeterminado) o Claude (`claude-opus-5-5`) con 7 herramientas analíticas limitadas | `generative_ai/` |
| Alertas | Reglas + ML + explicación IA; web (WebSocket) y correo | `notifications/` |
| Pruebas | pytest (47 pruebas, incluye integración con Ollama) | `tests/` |
| Despliegue | PowerShell; Docker Compose opcional; demo pública: frontend en **Vercel** + backend local por túnel **ngrok** | `deployment/`, `frontend/vercel.json` |

## Requisitos
- Windows 10/11, **SQL Server Express** (instancia `.\SQLEXPRESS`) con `sqlcmd` y **ODBC Driver 18**
- **Python 3.14**, **Node.js 20+**
- **Ollama** para el asistente de IA (ver abajo); alternativa: API key de Anthropic. (Opcional) Docker Desktop

### Asistente de IA con Ollama (local, sin costo)
```powershell
winget install Ollama.Ollama          # o descargar desde https://ollama.com/download
ollama pull qwen2.5:1.5b              # ~1 GB; el servicio queda escuchando en http://localhost:11434
curl http://localhost:11434/api/tags  # comprobar que el modelo aparece
```
En `.env`: `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=qwen2.5:1.5b` (valores por defecto). Para usar Claude en su lugar:
`LLM_PROVIDER=anthropic` y `ANTHROPIC_API_KEY=...`. Estado del proveedor: `GET /api/assistant/status`.
Con Ollama ningún dato sale del equipo. En CPU cada respuesta tarda ~15-60 s.

## Instalación rápida (≈ 3 minutos)
```powershell
git clone <repo> ; cd <repo>
copy .env.example .env        # complete JWT_SECRET y APP_USERS (y ANTHROPIC_API_KEY solo si usa Claude)
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
| Batería de 12 preguntas del asistente (proveedor configurado) | `python -m generative_ai.eval_assistant` |
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
Requiere `MSSQL_SA_PASSWORD`, `ETL_DB_PASSWORD` y `API_DB_PASSWORD` en `.env`. *Nota: los archivos Compose están preparados pero **no se ejecutaron completos**: Docker Desktop se instaló al final del proyecto y el equipo (7,7 GB de RAM) no tenía memoria suficiente para un segundo SQL Server en contenedor.*

## Despliegue público (Vercel + ngrok)
Demo en línea: **https://examen.jsanchez.site** (también `https://examen1-te-6gdu.vercel.app`).

```
Navegador ──► examen.jsanchez.site (Vercel: React compilado, estático)
    └── /api y /ws ──► https://bannister-crave-malformed.ngrok-free.dev (túnel ngrok)
                          └──► PC de desarrollo: FastAPI :8000 → SQL Server Express + Ollama
```
- **Solo el frontend** está en Vercel. El backend no puede ir a Vercel: depende de SQL Server Express y Ollama locales, de respuestas de hasta 60 s (asistente) y de WebSocket.
- **El sitio solo muestra datos mientras la PC de desarrollo está encendida** con el backend y el túnel abiertos.

**Configuración (una vez)**
1. Vercel → importar el repositorio → *Root Directory* `frontend` (preset Vite, fijado por `frontend/vercel.json`).
2. Variable de entorno en Vercel: `VITE_API_URL=https://<dominio-ngrok>`. Vacía en local (Vite redirige `/api` y `/ws`).
3. Dominio propio: proyecto → *Settings → Domains* → `examen.jsanchez.site` (DNS administrado por Vercel).
4. Backend (`.env`): agregar los orígenes públicos a `CORS_ORIGINS` (p. ej. `https://examen.jsanchez.site`). Sin esto el navegador bloquea las llamadas.
5. ngrok: `ngrok config add-authtoken <token>` (el token no se versiona) y reservar el dominio gratuito en el dashboard.

**Cada vez que se quiera publicar**
```powershell
powershell -ExecutionPolicy Bypass -File deployment\start.ps1      # backend :8000, frontend local y keep_warm
ngrok http --url=bannister-crave-malformed.ngrok-free.dev 8000   # deje la ventana abierta
```
Comprobación: `https://<dominio-ngrok>/api/health` → `{"status":"ok","database":"ok"}`. El frontend envía la cabecera `ngrok-skip-browser-warning` para evitar la página de aviso de ngrok gratuito.

**Velocidad:** con poca RAM libre, Windows saca de memoria las páginas de SQL Server y del modelo de Ollama tras unos minutos sin uso; medido: `/api/kpis` tardó 83 s en frío y 0,3-0,5 s en caliente (el túnel solo añade 0,1-0,3 s). `start.ps1` abre también `python -m deployment.keep_warm`, que cada 2 min repite (vía la API local, solo lectura) las consultas iniciales de cada pestaña y un ping mínimo a Ollama con el mismo `num_ctx`; no cierre esa ventana. Cerrar Docker Desktop (`wsl --shutdown`) y pestañas del navegador libera más RAM. No acelera preguntas al asistente con filtros nuevos ni el tiempo de generación del modelo (≈ 6-60 s en CPU).

**Riesgos:** la PC queda expuesta a internet a través de la API (con JWT, roles y límite de solicitudes al asistente). Use contraseñas fuertes en `APP_USERS` y cierre el túnel cuando no lo necesite.


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
| — | [Evidencias generadas](documentation/evidencias/) (perfil, diccionarios, cargas, KPIs, ML, pytest) |

## Solución de problemas
| Síntoma | Causa / solución |
|---|---|
| `CREATE INDEX failed … QUOTED_IDENTIFIER` | Ejecute `sqlcmd` con `-I` |
| `Data source name not found` | Instale *ODBC Driver 18 for SQL Server* o cambie `ODBC_DRIVER` en `.env` |
| Asistente responde 503 “No se pudo conectar con Ollama” | Inicie Ollama (aplicación o `ollama serve`) y verifique `OLLAMA_BASE_URL` |
| Asistente responde 503 “ollama pull …” | Descargue el modelo: `ollama pull qwen2.5:1.5b` |
| Asistente responde 503 con proveedor anthropic | Falta `ANTHROPIC_API_KEY` en `.env`; reinicie el backend |
| Asistente muy lento | Normal en CPU con modelos locales; reduzca `OLLAMA_NUM_CTX` o use preguntas más concretas |
| El dashboard muestra 401 | Token expirado: vuelva a iniciar sesión |
