# 11. Manual de usuario

## Ingreso
Abra `http://localhost:5173` e ingrese con el usuario asignado (definidos en `.env`, variable `APP_USERS`). Roles: **analyst** (consulta) y **admin** (además ejecuta pipeline, predicción y alertas de prueba). La sesión dura 8 horas.

La cabecera muestra siempre **“Datos actualizados: fecha y hora de la última carga ETL exitosa (hasta la última fecha con ventas)”**.

## Dashboard
1. **Filtros:** fechas desde/hasta, territorio, categoría de producto, categoría de cliente y grupo de compra. Todos los paneles se actualizan.
2. **KPIs:** ventas netas, ganancia, margen, facturas, ticket promedio y clientes activos, con la variación contra el período anterior de igual duración (verde sube, rojo baja). Pase el mouse sobre un KPI para ver su fórmula.
3. **Tendencia histórica:** elija año, trimestre, mes o semana.
4. **Ventas por dimensión:** elija la dimensión. **Drill-down:** haga clic en una barra de territorio (→ estados → ciudades), categoría (→ productos) o categoría de cliente (→ clientes). “Quitar drill-down” vuelve al inicio.
5. **Detalle:** líneas de venta paginadas que respetan todos los filtros.

> Las fechas posteriores al 2016-05-31 corresponden a operaciones **simuladas** para la demostración.

## Predicciones
Modelo activo (versión, algoritmo, conjuntos de datos), tabla de error del modelo vs líneas base por horizonte, gráfico real vs predicción en el período de prueba y pronóstico de las próximas 4 semanas por territorio. Todo lo de esta pestaña es **PREDICCIÓN**, no dato histórico.

## Asistente IA
Escriba una pregunta (máx. 500 caracteres) o use un ejemplo. La respuesta marca **DATO** (cifra del DW), **PREDICCIÓN** (modelo) e **INTERPRETACIÓN** (análisis de la IA). Despliegue “Fuentes” para ver qué consultas se hicieron. Si la información no existe, el asistente lo dice. Límite: 6 preguntas por minuto.

## Alertas
Lista con tipo (regla/ml), severidad, entidad, valor observado, umbral, período y estado. Haga clic en una alerta para ver mensaje, acción recomendada, explicación generada por IA (si existe) y entregas (web/correo). Cambie el estado con el selector (nueva → atendida → resuelta/descartada). Las alertas nuevas aparecen además como notificación emergente en cualquier pestaña. Administradores: *Evaluar reglas* y *Disparar alerta de prueba*.

## Operación
Estado de las cargas ETL (clic en una ejecución para ver sus pasos), calidad de datos, reconciliación entre capas, cuarentena, watermarks, modelo activo y notificaciones. Administradores: *Ejecutar pipeline*.
