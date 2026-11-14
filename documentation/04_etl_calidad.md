# 4. Extracción, staging, transformación y calidad

## Diagrama del pipeline
```mermaid
flowchart TD
    A[Inicio: ops.EtlExecution status=running] --> B{¿Hay watermarks?}
    B -- no --> C[Modo initial: extracción completa]
    B -- sí --> D[Modo incremental: col > watermark − 5 min]
    C & D --> E[12 objetos fuente → raw.* append-only<br/>lotes de 5 000 filas, _execution_id]
    E --> F[Por entidad: lote = raw de esta ejecución + claves en cuarentena pendientes]
    F --> G[Deduplicar: último watermark, último _raw_id]
    G --> H[Reglas de rechazo → quarantine.RejectedRecord]
    H --> I[Estandarizar / derivar / marcar outliers]
    I --> J[MERGE → clean.* (solo si cambió)]
    J --> K[Vistas ready.* integración]
    K --> L[Dimensiones SCD1/SCD2 → hechos MERGE]
    L --> M[Reconciliación + 9 métricas de calidad]
    M --> N[Commit de watermarks · status=success]
    N --> O[Predicción ML batch → evaluación de alertas → notificaciones]
    E & J & L -. error .-> X[status=failed, watermarks NO avanzan<br/>re-ejecutar es seguro]
```

## Objetos extraídos
| Fuente | Watermark | Clave | Filas iniciales |
|---|---|---|---|
| Application.Countries / StateProvinces / Cities | ValidFrom | *ID | 190 / 53 / 37 940 |
| Application.People | ValidFrom | PersonID | 1 111 |
| Sales.CustomerCategories / BuyingGroups / Customers | ValidFrom | *ID | 8 / 2 / 663 |
| Warehouse.StockGroups / StockItemStockGroups / StockItems | ValidFrom / LastEditedWhen | *ID | 10 / 442 / 227 |
| Sales.Invoices | LastEditedWhen | InvoiceID | 70 510 |
| Sales.InvoiceLines | LastEditedWhen | InvoiceLineID | 228 265 |

**Minimización:** no se extraen teléfonos, correos, fotos, contraseñas ni geografía espacial.

## Zonas de staging
| Zona | Regla aplicada |
|---|---|
| `raw` | Append-only; jamás se actualiza ni borra. Cada fila: `_raw_id`, `_execution_id`, `_extracted_at`. |
| `clean` | Una fila por clave de negocio; MERGE solo actualiza si algún valor cambió (`EXCEPT`) → idempotente. |
| `quarantine.RejectedRecord` | Registro completo en JSON + fuente, clave, regla, dimensión, ejecución y fecha; estado `pendiente/reprocesado`. |
| `ready` | Vistas que integran entidades (cliente + categoría + grupo + ciudad; producto + grupo principal) conservando claves naturales y linaje. |

## Catálogo de reglas de calidad y transformación
| ID | Objeto | Dimensión | Regla | Acción |
|---|---|---|---|---|
| R-CO/SP/CI/PE/CC/BG/SG-01 | catálogos | Completitud | Nombre obligatorio (tras recortar) | Cuarentena |
| R-CI-02 | Cities | Integridad | Ciudad sin estado | Cuarentena |
| R-CU-01 | Customers | Completitud | Nombre obligatorio | Cuarentena |
| R-CU-02/03 | Customers | Validez | Días de pago / límite de crédito negativos | Cuarentena |
| R-SISG-01 | StockItemStockGroups | Integridad | Relación incompleta | Cuarentena |
| R-SI-01/02 | StockItems | Completitud / Validez | Nombre obligatorio; precio de lista > 0 | Cuarentena |
| R-IN-01 | Invoices | Validez | Fecha nula, < 2013 o futura | Cuarentena |
| R-IN-02 | Invoices | Completitud | Factura sin cliente | Cuarentena |
| R-IL-01 | InvoiceLines | Validez | Cantidad ≤ 0 | Cuarentena |
| R-IL-02/03 | InvoiceLines | Validez | Precio negativo; tasa fuera de 0-100 | Cuarentena |
| R-IL-04 | InvoiceLines | Consistencia | `ExtendedPrice ≠ Qty×UnitPrice + Tax` (± 0,05) | Cuarentena |
| R-IL-05 | InvoiceLines | Integridad | Línea huérfana (factura inexistente) | Cuarentena **con reintento automático** |
| R-IL-06 | InvoiceLines | Completitud | Línea sin artículo | Cuarentena |
| T-01 | todos los textos | Limpieza | `LTRIM/RTRIM`, colapsar espacios dobles, vacío → NULL | Transformación |
| T-02 | StateProvinceCode | Estandarización | Mayúsculas | Transformación |
| T-03 | InvoiceLines.UnitPrice | Nulos (error de captura) | Si es NULL se **deriva** `(ExtendedPrice − TaxAmount)/Quantity` (regla confiable) y `IsUnitPriceDerived = 1` | Imputación documentada |
| T-04 | InvoiceLines.Quantity | Outliers | `Quantity > media + 4σ` (umbral ≈ 257) → `IsQuantityOutlier = 1`; **no se elimina** | Marca |
| T-05 | Cities.Population | Validez | Negativa → NULL (desconocido, no cero) | Transformación |
| DUP | todos | Unicidad | Clave de duplicidad = clave de negocio; supervivencia = mayor watermark, luego mayor `_raw_id` | Deduplicación |
| INT | Product (N:M) | Integración | Categoría principal = grupo con menor StockGroupID; lista completa en `AllCategories` | Evita multiplicar medidas |
| UNK | FactSales | Integridad referencial | Dimensión inexistente → miembro −1 y re-resolución posterior | Miembro desconocido |

## Manejo de nulos
| Campo | Clasificación | Decisión |
|---|---|---|
| Customers.BuyingGroupID | No aplica (cliente independiente) | Conservar NULL en clean; en DW `'Sin grupo de compra'` |
| Customers.CreditLimit | No aplica (sin límite) | Conservar NULL; **no** se reemplaza por 0 |
| StockItems.Brand | Desconocido | `'Sin marca'` |
| StockItems.Size | No aplica | `'N/A'` |
| InvoiceLines.UnitPrice | Error de captura con regla confiable | Derivar y marcar |
| Medidas numéricas | — | Nunca se reemplazan automáticamente por 0 |

## Carga inicial e incremental
- Watermark por objeto en `ops.Watermark`, **persistido solo al terminar con éxito** (`audit.commit_watermarks`).
- Ventana de solapamiento de 5 minutos para registros que llegan tarde a la fuente; los duplicados resultantes se eliminan por la regla de supervivencia y el MERGE no los vuelve a insertar.
- Cambios en dimensiones se detectan porque las tablas temporales actualizan `ValidFrom` en cada modificación.
- Upsert controlado (MERGE con `EXCEPT`) en clean y DW → **idempotencia**: re-ejecutar sin cambios inserta 0 y actualiza 0 (prueba automatizada).
- Conteos leídos/insertados/actualizados/rechazados por paso en `ops.EtlStepLog`.

## Auditoría mínima (guía → implementación)
| Campo de la guía | Columna |
|---|---|
| execution_id / pipeline_name | `ops.EtlExecution.ExecutionID`, `PipelineName` |
| start_time / end_time | `StartTime`, `EndTime` (ejecución y cada paso) |
| source_object / target_object | `ops.EtlStepLog.SourceObject`, `TargetObject` |
| rows_read / inserted / updated / rejected | `RowsRead`, `RowsInserted`, `RowsUpdated`, `RowsRejected` |
| status / error_detail | `Status`, `ErrorDetail` (traza completa en fallas) |
| watermark_start / watermark_end | `WatermarkStart`, `WatermarkEnd` |

## Evidencias
- Ejecuciones, pasos, reconciliación, cuarentena, SCD2 e imputación: [evidencias/04_resultados_carga.md](evidencias/04_resultados_carga.md)
- Perfil antes de la limpieza: [evidencias/01_perfil_fuente.md](evidencias/01_perfil_fuente.md)
- Log de texto: `etl/logs/pipeline.log`
