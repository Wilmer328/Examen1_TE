# Plataforma de Datos y Analítica - Wide World Importers

Proyecto del primer parcial de Tecnologías Emergentes.

La idea del proyecto es tomar los datos de ventas de una empresa (usé la base de ejemplo WideWorldImporters de Microsoft) y llevarlos desde la base transaccional hasta algo útil para tomar decisiones: un dashboard, un pronóstico de ventas, un asistente al que se le pueden hacer preguntas y alertas cuando las ventas caen.

El flujo es este:

1. Un proceso ETL en Python saca los datos de SQL Server de forma incremental.
2. Los datos pasan por un staging con cuatro zonas: `raw` (tal como llegan), `clean` (validados), `quarantine` (los que no pasan las reglas de calidad) y `ready` (listos para cargar).
3. Se cargan en un Data Warehouse con modelo estrella.
4. Una API en FastAPI expone los datos al dashboard hecho en React.
5. Un modelo de Machine Learning pronostica las ventas semanales por territorio.
6. Un asistente con IA generativa responde preguntas sobre los datos.
7. Después de cada carga se revisan reglas de alerta y se notifica por la web y por correo.

Demo en línea: https://examen.jsanchez.site (solo funciona cuando mi PC tiene el backend encendido, más abajo explico por qué).

## Tecnologías

- **Base de datos:** SQL Server 2025 Express (fuente, staging y Data Warehouse)
- **ETL:** Python 3.14 y SQL
- **API:** FastAPI con autenticación JWT
- **Dashboard:** React 18, Vite y Apache ECharts
- **Machine Learning:** scikit-learn
- **IA generativa:** Ollama con el modelo `qwen2.5:1.5b` corriendo en local. También se puede usar Claude cambiando una variable.
- **Pruebas:** pytest (47 pruebas)
- **Publicación:** Vercel para el frontend y ngrok para exponer el backend

## Estructura del repositorio

```
database/          scripts SQL (bases, staging, Data Warehouse, procedimientos, seguridad)
etl/               extracción, transformación, carga y simulador de cambios
common/            configuración, conexión y consultas analíticas compartidas
backend/           API en FastAPI
frontend/          dashboard en React
machine_learning/  variables, entrenamiento y predicción
generative_ai/     asistente y verificación de cifras
notifications/     reglas de alerta y envío de notificaciones
tests/             pruebas automatizadas
deployment/        scripts para instalar, iniciar y programar el pipeline; Docker Compose
documentation/     documentación del proyecto y evidencias
```

## Qué se necesita

- Windows 10 u 11
- SQL Server Express (instancia `.\SQLEXPRESS`), `sqlcmd` y ODBC Driver 18
- Python 3.14 y Node.js 20 o superior
- Ollama para el asistente

Para instalar Ollama y el modelo:

```powershell
winget install Ollama.Ollama
ollama pull qwen2.5:1.5b
```

El modelo pesa alrededor de 1 GB. Corre en la CPU, así que cada respuesta tarda entre 10 segundos y un minuto, pero tiene la ventaja de que los datos no salen de la computadora y no tiene costo. Si se prefiere usar Claude, en el `.env` se pone `LLM_PROVIDER=anthropic` y la `ANTHROPIC_API_KEY`.

## Instalación

```powershell
git clone https://github.com/Wilmer328/Examen1_TE.git
cd Examen1_TE
copy .env.example .env
```

En el `.env` hay que completar `JWT_SECRET` y los usuarios de `APP_USERS`. Después:

```powershell
powershell -ExecutionPolicy Bypass -File deployment\setup.ps1
```

Este script crea el entorno de Python, instala el frontend, descarga y restaura WideWorldImporters, ejecuta los scripts SQL en orden, hace la carga inicial, entrena el modelo y genera las primeras predicciones y alertas.

Si se prefiere hacerlo a mano:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

sqlcmd -S .\SQLEXPRESS -E -C -I -i database\00_create_databases.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\staging\01_staging_schema.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\data-warehouse\02_dw_schema.sql
sqlcmd -S .\SQLEXPRESS -E -C -I -i database\data-warehouse\03_dw_load_procs.sql

.\.venv\Scripts\python -m etl.pipeline --mode initial
.\.venv\Scripts\python -m machine_learning.train
.\.venv\Scripts\python -m machine_learning.predict
.\.venv\Scripts\python -m notifications.alerts
```

El `-I` en `sqlcmd` es necesario; sin él falla la creación de algunos índices.

## Cómo levantarlo

```powershell
powershell -ExecutionPolicy Bypass -File deployment\start.ps1
```

Abre tres ventanas: el backend (puerto 8000), el frontend (http://localhost:5173) y `keep_warm`, que explico más abajo. La documentación de la API queda en http://localhost:8000/docs.

## Comandos útiles

| Para qué | Comando |
|---|---|
| Correr una carga incremental (incluye predicción y alertas) | `python -m etl.pipeline` |
| Programar la carga cada 15 minutos | `deployment\programar_pipeline.ps1` |
| Simular ventas nuevas para probar el incremental | `python -m etl.simulate_source_changes --days 7` |
| Provocar una falla y probar la recuperación | `python -m etl.pipeline --fail-at load_facts` |
| Disparar una alerta de prueba | `python -m notifications.alerts --test` |
| Correr las pruebas | `python -m pytest -v tests` |
| Evaluar el asistente con 12 preguntas | `python -m generative_ai.eval_assistant` |
| Volver al estado inicial | `deployment\reset_environment.ps1` |

Los datos que crea el simulador quedan marcados como `SIMULADO` para no confundirlos con los reales.

## Seguridad

- Las contraseñas y claves van en el `.env`, que no se sube al repositorio. El `.env.example` sirve como plantilla.
- El navegador nunca se conecta directo a SQL Server; todo pasa por la API y las consultas usan parámetros.
- El asistente no puede escribir SQL. Solo puede elegir entre siete consultas ya definidas y el servidor valida los parámetros antes de ejecutarlas.
- Dejé preparadas dos cuentas de base de datos con permisos mínimos (`etl_user` y `api_user`). Para activarlas hay que correr `deployment\habilitar_sql_auth.ps1` como administrador y poner `SQL_AUTH=sql` en el `.env`. En mi equipo no las activé porque SQL Server estaba solo con autenticación de Windows.

## Publicación en internet

El frontend está en Vercel con mi dominio (https://examen.jsanchez.site). El backend no lo pude subir a Vercel porque necesita el SQL Server y el Ollama que corren en mi computadora, así que lo expongo con un túnel de ngrok:

```
navegador -> examen.jsanchez.site (Vercel, frontend)
          -> túnel ngrok -> mi PC (FastAPI -> SQL Server y Ollama)
```

Por eso la página solo muestra datos mientras mi PC está encendida con el backend y el túnel abiertos. Para levantar el túnel:

```powershell
ngrok http --url=bannister-crave-malformed.ngrok-free.dev 8000
```

Para configurarlo desde cero:

1. En Vercel, importar el repositorio y elegir `frontend` como carpeta raíz.
2. Agregar la variable `VITE_API_URL` con la dirección del túnel de ngrok.
3. En el `.env` del backend, agregar el dominio público a `CORS_ORIGINS`. Si no se hace, el navegador bloquea las peticiones.

## Sobre la velocidad

Mi computadora tiene 8 GB de RAM y suele quedarse con menos de 1 GB libre. Después de unos minutos sin uso, Windows saca de la memoria a SQL Server y al modelo de IA, y la siguiente consulta puede tardar más de un minuto. Una vez cargado, todo responde en menos de medio segundo.

Para evitarlo hice `deployment/keep_warm.py`, que cada dos minutos repite las consultas principales del dashboard y le hace una petición mínima a Ollama. `start.ps1` lo abre automáticamente; hay que dejar esa ventana abierta.

## Docker

En `deployment/docker-compose.yml` está la configuración para levantar todo con contenedores:

```powershell
docker compose -f deployment/docker-compose.yml --env-file .env up -d --build sqlserver
docker compose -f deployment/docker-compose.yml --env-file .env run --rm init
docker compose -f deployment/docker-compose.yml --env-file .env run --rm etl
docker compose -f deployment/docker-compose.yml --env-file .env up -d api frontend
```

Necesita `MSSQL_SA_PASSWORD`, `ETL_DB_PASSWORD` y `API_DB_PASSWORD` en el `.env`. No lo llegué a probar completo porque mi equipo no tiene memoria suficiente para correr un segundo SQL Server dentro de Docker.

## Documentación

1. [Alcance y requerimientos](documentation/01_alcance_requerimientos.md)
2. [Arquitectura y decisiones técnicas](documentation/02_arquitectura.md)
3. [Modelo dimensional](documentation/03_modelo_dimensional.md)
4. [ETL y calidad de datos](documentation/04_etl_calidad.md)
5. [KPIs, dashboard y API](documentation/05_bi_kpis_api.md)
6. [Machine Learning](documentation/06_machine_learning.md)
7. [IA generativa](documentation/07_generative_ai.md)
8. [Alertas y automatización](documentation/08_alertas_automatizacion.md)
9. [Seguridad y operación](documentation/09_seguridad_operacion.md)
10. [Plan de pruebas](documentation/10_plan_pruebas.md)
11. [Manual de usuario](documentation/11_manual_usuario.md)

En [documentation/evidencias](documentation/evidencias/) están los resultados de las cargas, la validación de los KPIs, las pruebas del asistente y el resultado de pytest.

## Problemas comunes

- **Error de `QUOTED_IDENTIFIER` al crear índices:** falta el `-I` en `sqlcmd`.
- **`Data source name not found`:** falta instalar ODBC Driver 18 o cambiar `ODBC_DRIVER` en el `.env`.
- **El asistente dice que no se puede conectar con Ollama:** hay que abrir la aplicación de Ollama.
- **El asistente pide hacer `ollama pull`:** falta descargar el modelo con `ollama pull qwen2.5:1.5b`.
- **El dashboard devuelve 401:** la sesión expiró, hay que volver a iniciar sesión.
- **`127.0.0.1:5173` no abre:** usar `localhost:5173`.
