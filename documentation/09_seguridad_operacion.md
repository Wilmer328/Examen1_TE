# 9. Seguridad, calidad, operación y monitoreo

## Seguridad mínima
| Control | Implementación |
|---|---|
| Sin contraseñas en el repositorio | `.env` en `.gitignore`; `.env.example` sin valores; contraseñas SQL se pasan como variables de `sqlcmd` |
| Mínimo privilegio | `database/security/04_security.sql`: `etl_user` (lee fuente; escribe staging/DW; sin DDL) y `api_user` (solo lectura del DW + escritura acotada en alertas/predicciones/log IA; `DENY` sobre `dw`). Se activan con `deployment/habilitar_sql_auth.ps1` (requiere administrador) y `SQL_AUTH=sql` |
| Inyección SQL | Todo valor externo va como parámetro `?`; nombres de columnas solo desde listas blancas; el LLM no genera SQL |
| Endpoints protegidos | JWT HS256 con expiración; rol `admin` para ejecutar pipeline, predicción, evaluación y alerta de prueba; WebSocket exige token |
| Frontend nunca habla con SQL Server | El navegador llama a `/api` (proxy Vite/nginx en local; en la demo pública, a la URL de `VITE_API_URL`) |
| Exposición pública (Vercel + ngrok) | Solo se expone la API (puerto 8000) por HTTPS; SQL Server y Ollama no salen de la PC. CORS limitado a los orígenes de `CORS_ORIGINS` (verificado: un origen no autorizado recibe 400). El authtoken de ngrok vive en el perfil local de ngrok, fuera del repositorio. **Riesgo residual:** cualquiera con el enlace puede intentar iniciar sesión; no hay bloqueo por intentos fallidos en `/api/auth/login` (solo el asistente tiene límite por minuto) |
| Datos de muestra | WWI es un dataset ficticio de Microsoft; no se extraen correos, teléfonos ni fotos |
| Información enviada a IA externa | Solo agregados (montos, conteos, nombres de categorías/territorios/empresas ficticias) y la pregunta del usuario. Documentado en `07_generative_ai.md` |

> **Pendiente de entorno:** en el equipo de desarrollo SQL Server estaba en modo solo-Windows y la sesión no tenía privilegios de administrador; por eso la demo usa autenticación integrada. El script de cuentas técnicas está listo y probado sintácticamente; ejecutarlo como administrador habilita el modo de mínimo privilegio sin cambiar código (solo `.env`). Limitación conocida: los endpoints *admin* que reentrenan/evalúan desde la API usan la conexión ETL.

## Monitoreo (pestaña *Operación* / `GET /api/ops/summary`)
Muestra: ejecuciones ETL (estado, duración, filas extraídas/rechazadas, hechos insertados, error), pasos por ejecución con watermarks, hora de la última carga exitosa, 9 métricas de calidad, reconciliación entre capas, cuarentena, watermarks, modelo activo, estado de notificaciones y uso del asistente.

| Dimensión de calidad | Métrica implementada |
|---|---|
| Completitud | DQ-01 % clientes con nombre/categoría/ciudad; DQ-02 % precios no derivados |
| Unicidad | DQ-03 claves `InvoiceLineID` duplicadas en DW; DQ-04 clientes con > 1 versión vigente |
| Validez | DQ-05 líneas con cantidad/neto ≤ 0 |
| Consistencia | DQ-06 % líneas con Gross = Net + Tax |
| Integridad | DQ-07 hechos con miembro desconocido; DQ-08 registros pendientes en cuarentena |
| Oportunidad | DQ-09 minutos entre inicio de la ejecución y disponibilidad en el DW |

## Continuidad y recuperación (runbook)
| Situación | Procedimiento |
|---|---|
| Reiniciar el pipeline | `.\.venv\Scripts\python.exe -m etl.pipeline` (modo automático: incremental) |
| Reintentar una carga fallida | Volver a ejecutar el mismo comando. La ejecución fallida quedó `failed` sin avanzar watermarks; el MERGE evita duplicados. Demostración: `python -m etl.pipeline --fail-at load_facts` y luego `python -m etl.pipeline` (prueba `test_controlled_failure_does_not_advance_watermark_and_recovers`) |
| Reprocesar cuarentena | Corregir el dato en la fuente; la siguiente carga reevalúa automáticamente las claves `pendiente` |
| Reintentar notificaciones | `python -m notifications.alerts --retry` |
| Recarga completa del DW | `python -m etl.pipeline --mode initial` |
| Restaurar la base de prueba y reconstruir todo | `deployment\reset_environment.ps1` (elimina Staging/DW, restaura WWI original, ejecuta `setup.ps1`) |
| Reconstruir desde cero en otra máquina | `deployment\setup.ps1` (o `docker compose` con el servicio `init`) |

Scripts SQL en orden de ejecución: `00_create_databases.sql` → `staging/01_staging_schema.sql` → `data-warehouse/02_dw_schema.sql` → `data-warehouse/03_dw_load_procs.sql` → `security/04_security.sql` (opcional). Usar `sqlcmd -I` (QUOTED_IDENTIFIER ON, requerido por el índice filtrado).
