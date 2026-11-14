# Resultados de carga, reconciliación y calidad

Generado automáticamente el 2026-11-14 13:49 por `documentation/generar_evidencias.py`.

## Ejecuciones ETL

| ExecutionID | Mode | TriggeredBy | StartTime | EndTime | seg | Status | error |
|---|---|---|---|---|---|---|---|
| 1 | initial | manual | 2026-11-14 13:14:00.734079 | 2026-11-14 13:14:40.589833 | 40 | success |  |
| 2 | incremental | manual | 2026-11-14 13:15:32.493498 | 2026-11-14 13:15:43.097341 | 11 | success |  |
| 3 | incremental | manual | 2026-11-14 13:16:03.366918 | 2026-11-14 13:16:10.724279 | 7 | success |  |
| 4 | incremental | manual | 2026-11-14 13:16:11.647736 | 2026-11-14 13:16:18.409980 | 7 | success |  |
| 5 | incremental | manual | 2026-11-14 13:16:25.637737 | 2026-11-14 13:16:32.629512 | 7 | success |  |
| 6 | incremental | manual | 2026-11-14 13:16:44.044801 | 2026-11-14 13:16:52.168516 | 8 | success |  |
| 7 | incremental | pytest | 2026-11-14 13:24:23.340562 | 2026-11-14 13:25:38.692477 | 75 | success |  |
| 8 | incremental | pytest-falla | 2026-11-14 13:25:38.861413 | 2026-11-14 13:25:46.448074 | 8 | failed | Falla SIMULADA en el paso 'load_facts' (--fail-at) |
| 9 | incremental | pytest-reintento | 2026-11-14 13:25:46.452513 | 2026-11-14 13:27:19.315430 | 93 | success |  |
| 10 | incremental | pytest | 2026-11-14 13:43:41.684712 | 2026-11-14 13:47:50.429356 | 249 | failed | Ejecución abandonada (proceso interrumpido por espera de memoria RESOURCE_SEMAPH |
| 11 | incremental | manual | 2026-11-14 13:47:51.278344 | 2026-11-14 13:47:57.829143 | 6 | success |  |
| 12 | incremental | manual | 2026-11-14 13:48:21.217896 | 2026-11-14 13:48:27.083684 | 6 | success |  |
| 13 | incremental | pytest | 2026-11-14 13:48:41.724057 | 2026-11-14 13:48:48.771558 | 7 | success |  |
| 14 | incremental | pytest-falla | 2026-11-14 13:48:48.956628 | 2026-11-14 13:48:53.712110 | 5 | failed | Falla SIMULADA en el paso 'load_facts' (--fail-at) |
| 15 | incremental | pytest-reintento | 2026-11-14 13:48:53.720217 | 2026-11-14 13:48:59.487804 | 6 | success |  |

## Pasos — Carga inicial (ejecución 1)

| StepName | RowsRead | RowsInserted | RowsUpdated | RowsRejected | WatermarkStart | WatermarkEnd | Status |
|---|---|---|---|---|---|---|---|
| extract:Countries | 190.0 | 190 |  |  |  | 2022-10-07 22:01:58.622602 | success |
| extract:StateProvinces | 53.0 | 53 |  |  |  | 2015-07-01 16:00:00 | success |
| extract:Cities | 37940.0 | 37940 |  |  |  | 2015-07-01 16:00:00 | success |
| extract:People | 1111.0 | 1111 |  |  |  | 2016-05-31 23:14:00 | success |
| extract:CustomerCategories | 8.0 | 8 |  |  |  | 2014-01-01 16:15:00 | success |
| extract:BuyingGroups | 2.0 | 2 |  |  |  | 2013-01-01 00:00:00 | success |
| extract:Customers | 663.0 | 663 |  |  |  | 2016-05-07 00:00:00 | success |
| extract:StockGroups | 10.0 | 10 |  |  |  | 2016-01-01 16:00:00 | success |
| extract:StockItemStockGroups | 442.0 | 442 |  |  |  | 2016-01-05 00:00:00 | success |
| extract:StockItems | 227.0 | 227 |  |  |  | 2016-05-31 23:12:00 | success |
| extract:Invoices | 70510.0 | 70510 |  |  |  | 2016-05-31 12:00:00 | success |
| extract:InvoiceLines | 228265.0 | 228265 |  |  |  | 2016-05-31 12:00:00 | success |
| clean:Countries | 190.0 | 190 | 0.0 | 0.0 |  | NaT | success |
| clean:StateProvinces | 53.0 | 53 | 0.0 | 0.0 |  | NaT | success |
| clean:Cities | 37940.0 | 37940 | 0.0 | 0.0 |  | NaT | success |
| clean:People | 1111.0 | 1111 | 0.0 | 0.0 |  | NaT | success |
| clean:CustomerCategories | 8.0 | 8 | 0.0 | 0.0 |  | NaT | success |
| clean:BuyingGroups | 2.0 | 2 | 0.0 | 0.0 |  | NaT | success |
| clean:Customers | 663.0 | 663 | 0.0 | 0.0 |  | NaT | success |
| clean:StockGroups | 10.0 | 10 | 0.0 | 0.0 |  | NaT | success |
| clean:StockItemStockGroups | 442.0 | 442 | 0.0 | 0.0 |  | NaT | success |
| clean:StockItems | 227.0 | 227 | 0.0 | 0.0 |  | NaT | success |
| clean:Invoices | 70510.0 | 70510 | 0.0 | 0.0 |  | NaT | success |
| clean:InvoiceLines | 228265.0 | 228265 | 0.0 | 0.0 |  | NaT | success |
| load:dw.DimDate |  | 5113 | 0.0 |  |  | NaT | success |
| load:dw.DimGeography |  | 37940 | 0.0 |  |  | NaT | success |
| load:dw.DimCustomer |  | 663 | 0.0 |  |  | NaT | success |
| load:dw.DimProduct |  | 227 | 0.0 |  |  | NaT | success |
| load:dw.DimEmployee |  | 19 | 0.0 |  |  | NaT | success |
| load:dw.FactSales | 228265.0 | 228265 | 0.0 |  |  | NaT | success |
| reconcile:InvoiceLines | 228265.0 | 228265 |  | 0.0 |  | NaT | success |

## Pasos — Carga incremental con cambios simulados (ejecución 6)

| StepName | RowsRead | RowsInserted | RowsUpdated | RowsRejected | WatermarkStart | WatermarkEnd | Status |
|---|---|---|---|---|---|---|---|
| extract:Countries | 1.0 | 1 |  |  | 2022-10-07 21:56:58.622602 | 2022-10-07 22:01:58.622602 | success |
| extract:StateProvinces | 10.0 | 10 |  |  | 2015-07-01 15:55:00 | 2015-07-01 16:00:00 | success |
| extract:Cities | 13.0 | 13 |  |  | 2015-07-01 15:55:00 | 2015-07-01 16:00:00 | success |
| extract:People | 182.0 | 182 |  |  | 2016-05-31 23:09:00 | 2016-05-31 23:14:00 | success |
| extract:CustomerCategories | 1.0 | 1 |  |  | 2014-01-01 16:10:00 | 2014-01-01 16:15:00 | success |
| extract:BuyingGroups | 2.0 | 2 |  |  | 2012-12-31 23:55:00 | 2013-01-01 00:00:00 | success |
| extract:Customers | 2.0 | 2 |  |  | 2016-05-06 23:55:00 | 2026-11-14 19:16:43.185073 | success |
| extract:StockGroups | 1.0 | 1 |  |  | 2016-01-01 15:55:00 | 2016-01-01 16:00:00 | success |
| extract:StockItemStockGroups | 2.0 | 2 |  |  | 2016-01-04 23:55:00 | 2016-01-05 00:00:00 | success |
| extract:StockItems | 143.0 | 143 |  |  | 2016-05-31 23:07:00 | 2016-05-31 23:12:00 | success |
| extract:Invoices | 580.0 | 580 |  |  | 2016-05-31 11:55:00 | 2026-11-14 13:16:42.967707 | success |
| extract:InvoiceLines | 1903.0 | 1903 |  |  | 2016-05-31 11:55:00 | 2026-11-14 13:16:43.123585 | success |
| clean:Countries | 1.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:StateProvinces | 10.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:Cities | 13.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:People | 182.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:CustomerCategories | 1.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:BuyingGroups | 2.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:Customers | 2.0 | 0 | 1.0 | 0.0 | NaT | NaT | success |
| clean:StockGroups | 1.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:StockItemStockGroups | 2.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:StockItems | 143.0 | 0 | 0.0 | 0.0 | NaT | NaT | success |
| clean:Invoices | 580.0 | 496 | 0.0 | 0.0 | NaT | NaT | success |
| clean:InvoiceLines | 1903.0 | 1617 | 0.0 | 2.0 | NaT | NaT | success |
| load:dw.DimDate |  | 0 | 0.0 |  | NaT | NaT | success |
| load:dw.DimGeography |  | 0 | 0.0 |  | NaT | NaT | success |
| load:dw.DimCustomer |  | 1 | 1.0 |  | NaT | NaT | success |
| load:dw.DimProduct |  | 0 | 0.0 |  | NaT | NaT | success |
| load:dw.DimEmployee |  | 0 | 0.0 |  | NaT | NaT | success |
| load:dw.FactSales | 1617.0 | 1617 | 0.0 |  | NaT | NaT | success |
| reconcile:InvoiceLines | 229884.0 | 229882 |  | 2.0 | NaT | NaT | success |

## Reconciliación (última)

| ExecutionID | Layer | ObjectName | RowCountValue | AmountValue | Notes |
|---|---|---|---|---|---|
| 15 | 1-fuente | WideWorldImporters.Sales.InvoiceLines | 229884 | 173421215.25 | Neto = ExtendedPrice - TaxAmount |
| 15 | 2-raw | WWI_Staging.raw.InvoiceLines (claves distintas) | 229884 |  | Raw es append-only: se cuentan claves distintas |
| 15 | 3b-cuarentena | WWI_Staging.quarantine (InvoiceLines pendientes) | 2 |  | Rechazadas por reglas de calidad |
| 15 | 3-clean | WWI_Staging.clean.InvoiceLines | 229882 | 173420219.25 |  |
| 15 | 4-dw | WWI_DW.dw.FactSales | 229882 | 173420219.25 |  |

## Calidad de datos (última ejecución)

| RuleID | QualityDimension | ObjectName | Description | MetricValue | Threshold | Passed |
|---|---|---|---|---|---|---|
| DQ-01 | Completitud | clean.Customers | % clientes con nombre, categoría y ciudad | 100.0000 | 100.0000 | True |
| DQ-02 | Completitud | clean.InvoiceLines | % líneas con precio unitario original (no derivado) | 99.9996 | 99.0000 | True |
| DQ-03 | Unicidad | dw.FactSales | Claves InvoiceLineID duplicadas en el DW | 0.0000 | 0.0000 | True |
| DQ-04 | Unicidad | dw.DimCustomer | Clientes con más de una versión vigente (SCD2) | 0.0000 | 0.0000 | True |
| DQ-05 | Validez | dw.FactSales | Líneas con cantidad o importe neto no positivo | 0.0000 | 0.0000 | True |
| DQ-06 | Consistencia | dw.FactSales | % líneas donde Gross = Net + Tax | 100.0000 | 100.0000 | True |
| DQ-07 | Integridad | dw.FactSales | Hechos asignados a miembro desconocido (-1) | 0.0000 | 0.0000 | True |
| DQ-08 | Integridad | quarantine | Registros pendientes en cuarentena | 2.0000 | 0.0000 | False |
| DQ-09 | Oportunidad | dw.FactSales | Minutos entre la ejecución y la disponibilidad en el DW (esta carga) | 0.0000 | 15.0000 | True |

## Cuarentena

| RejectedID | ExecutionID | SourceObject | BusinessKey | RuleID | RuleDescription | Status | registro |
|---|---|---|---|---|---|---|---|
| 1 | 6 | Sales.InvoiceLines | 229882 | R-IL-01 | Cantidad debe ser > 0 (no existen notas de crédito en el alcance) | pendiente | {"_raw_id":231302,"InvoiceLineID":229882,"InvoiceID":71092,"StockItemID":1,"Desc |
| 2 | 6 | Sales.InvoiceLines | 229884 | R-IL-04 | ExtendedPrice <> Quantity*UnitPrice + TaxAmount (tolerancia 0.05) | pendiente | {"_raw_id":231304,"InvoiceLineID":229884,"InvoiceID":71092,"StockItemID":3,"Desc |

## SCD Tipo 2 — clientes con historia

| CustomerKey | CustomerID | CustomerName | CustomerCategory | BuyingGroup | ValidFrom | ValidTo | IsCurrent |
|---|---|---|---|---|---|---|---|
| 340 | 1 | Tailspin Toys (Head Office) | Novelty Shop | Tailspin Toys | 1900-01-01 | 2026-11-14 | False |
| 664 | 1 | Tailspin Toys (Head Office) | Supermarket | Tailspin Toys | 2026-11-14 | 9999-12-31 | True |

## Imputación documentada (precio derivado)

| InvoiceLineID | Quantity | UnitPrice | ExtendedPrice | TaxAmount | IsUnitPriceDerived | Description |
|---|---|---|---|---|---|---|
| 229883 | 4 | 10.00 | 46.00 | 6.00 | True | SIMULADO precio nulo |

## Conteo de filas en el DW

| t | n |
|---|---|
| FactSales | 229882 |
| DimCustomer | 665 |
| DimProduct | 228 |
| DimEmployee | 20 |
| DimGeography | 37941 |
| DimDate | 5113 |

## Alertas y entregas

| AlertID | CreatedAt | AlertType | Severity | Entity | ObservedValue | ThresholdValue | PeriodStart | Origin | IsSimulated | Status | Channel | entrega | Attempts | detalle |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-14 13:21:14.396903 | regla | alta | Territorio Far West | 72468.15 | 108355.40 | 2016-05-30 | Regla R-ALR-01 | True | nueva | email | entregado | 1 | SIMULADO (sin SMTP): notifications\outbox\alerta_1_202611141 |
| 1 | 2026-11-14 13:21:14.396903 | regla | alta | Territorio Far West | 72468.15 | 108355.40 | 2016-05-30 | Regla R-ALR-01 | True | nueva | web | entregado | 1 | Publicada en ops.Alert / WebSocket |
| 2 | 2026-11-14 13:21:19.718183 | regla | media | Territorio New England | 47821.25 | 51663.64 | 2016-05-30 | Regla R-ALR-01 | True | nueva | email | entregado | 1 | SIMULADO (sin SMTP): notifications\outbox\alerta_2_202611141 |
| 2 | 2026-11-14 13:21:19.718183 | regla | media | Territorio New England | 47821.25 | 51663.64 | 2016-05-30 | Regla R-ALR-01 | True | nueva | web | entregado | 1 | Publicada en ops.Alert / WebSocket |
| 3 | 2026-11-14 13:21:19.818738 | regla | media | Territorio Rocky Mountain | 57888.80 | 63285.29 | 2016-05-30 | Regla R-ALR-01 | True | nueva | email | entregado | 1 | SIMULADO (sin SMTP): notifications\outbox\alerta_3_202611141 |
| 3 | 2026-11-14 13:21:19.818738 | regla | media | Territorio Rocky Mountain | 57888.80 | 63285.29 | 2016-05-30 | Regla R-ALR-01 | True | nueva | web | entregado | 1 | Publicada en ops.Alert / WebSocket |

