# Diccionario de datos — Data Warehouse WWI_DW

Generado automáticamente el 2026-11-14 13:49 por `documentation/generar_evidencias.py`.

## ai.AssistantLog

| columna | tipo | nulo | clave |
|---|---|---|---|
| LogID | bigint | no | PK |
| AskedAt | datetime2 | no |  |
| Username | nvarchar(50) | no |  |
| Question | nvarchar(600) | no |  |
| ToolsJson | nvarchar(max) | sí |  |
| Status | nvarchar(30) | no |  |
| AnswerChars | int | sí |  |
| LatencyMs | int | sí |  |
| InputTokens | int | sí |  |
| OutputTokens | int | sí |  |
| Model | nvarchar(60) | sí |  |
| ErrorDetail | nvarchar(1000) | sí |  |

## dw.DimCustomer

| columna | tipo | nulo | clave |
|---|---|---|---|
| CustomerKey | int | no | PK |
| CustomerID | int | no |  |
| CustomerName | nvarchar(100) | no |  |
| BillToCustomerID | int | sí |  |
| CustomerCategory | nvarchar(50) | no |  |
| BuyingGroup | nvarchar(50) | no |  |
| CityID | int | sí |  |
| GeographyKey | int | no |  |
| CreditLimit | decimal(18,2) | sí |  |
| PaymentDays | int | sí |  |
| IsOnCreditHold | bit | sí |  |
| ValidFrom | date | no |  |
| ValidTo | date | no |  |
| IsCurrent | bit | no |  |
| Scd2Hash | varbinary | no |  |
| ExecutionID | int | sí |  |
| UpdatedAt | datetime2 | no |  |

## dw.DimDate

| columna | tipo | nulo | clave |
|---|---|---|---|
| DateKey | int | no | PK |
| Date | date | no |  |
| Day | tinyint | no |  |
| DayName | nvarchar(15) | no |  |
| DayOfWeekIso | tinyint | no |  |
| WeekStart | date | no |  |
| IsoWeek | tinyint | no |  |
| Month | tinyint | no |  |
| MonthName | nvarchar(15) | no |  |
| YearMonth | char(7) | no |  |
| Quarter | tinyint | no |  |
| YearQuarter | char(7) | no |  |
| Year | smallint | no |  |
| IsWeekend | bit | no |  |

## dw.DimEmployee

| columna | tipo | nulo | clave |
|---|---|---|---|
| EmployeeKey | int | no | PK |
| EmployeeID | int | no |  |
| EmployeeName | nvarchar(50) | no |  |
| PreferredName | nvarchar(50) | sí |  |
| Role | nvarchar(20) | no |  |
| ExecutionID | int | sí |  |
| UpdatedAt | datetime2 | no |  |

## dw.DimGeography

| columna | tipo | nulo | clave |
|---|---|---|---|
| GeographyKey | int | no | PK |
| CityID | int | no |  |
| City | nvarchar(50) | no |  |
| StateProvinceCode | nvarchar(5) | no |  |
| StateProvince | nvarchar(50) | no |  |
| SalesTerritory | nvarchar(50) | no |  |
| Country | nvarchar(60) | no |  |
| Continent | nvarchar(30) | no |  |
| Region | nvarchar(30) | no |  |
| Subregion | nvarchar(30) | no |  |
| Population | bigint | sí |  |
| ExecutionID | int | sí |  |
| UpdatedAt | datetime2 | no |  |

## dw.DimProduct

| columna | tipo | nulo | clave |
|---|---|---|---|
| ProductKey | int | no | PK |
| StockItemID | int | no |  |
| ProductName | nvarchar(100) | no |  |
| Category | nvarchar(50) | no |  |
| AllCategories | nvarchar(400) | no |  |
| Brand | nvarchar(50) | no |  |
| Size | nvarchar(20) | no |  |
| IsChillerStock | bit | sí |  |
| ListUnitPrice | decimal(18,2) | sí |  |
| RecommendedRetailPrice | decimal(18,2) | sí |  |
| ExecutionID | int | sí |  |
| UpdatedAt | datetime2 | no |  |

## dw.FactSales

| columna | tipo | nulo | clave |
|---|---|---|---|
| SalesKey | bigint | no | PK |
| InvoiceLineID | int | no |  |
| InvoiceID | int | no |  |
| DateKey | int | no |  FK?dw.DimDate |
| CustomerKey | int | no |  FK?dw.DimCustomer |
| ProductKey | int | no |  FK?dw.DimProduct |
| EmployeeKey | int | no |  FK?dw.DimEmployee |
| GeographyKey | int | no |  FK?dw.DimGeography |
| Quantity | int | no |  |
| UnitPrice | decimal(18,2) | no |  |
| TaxRate | decimal(18,3) | no |  |
| NetAmount | decimal(18,2) | no |  |
| TaxAmount | decimal(18,2) | no |  |
| GrossAmount | decimal(18,2) | no |  |
| LineProfit | decimal(18,2) | no |  |
| IsUnitPriceDerived | bit | no |  |
| ExecutionID | int | sí |  |
| LoadedAt | datetime2 | no |  |
| UpdatedAt | datetime2 | sí |  |

## ml.BacktestResult

| columna | tipo | nulo | clave |
|---|---|---|---|
| ModelVersion | nvarchar(50) | no | PK |
| SalesTerritory | nvarchar(50) | no | PK |
| WeekStart | date | no | PK |
| SplitName | nvarchar(10) | no |  |
| ActualNetAmount | decimal(19,2) | no |  |
| PredictedNetAmount | decimal(19,2) | no |  |
| BaselineNetAmount | decimal(19,2) | no |  |

## ml.ModelRegistry

| columna | tipo | nulo | clave |
|---|---|---|---|
| ModelVersion | nvarchar(50) | no | PK |
| ModelName | nvarchar(100) | no |  |
| Algorithm | nvarchar(100) | no |  |
| TrainedAt | datetime2 | no |  |
| TrainStart | date | no |  |
| TrainEnd | date | no |  |
| ValidStart | date | no |  |
| ValidEnd | date | no |  |
| TestStart | date | no |  |
| TestEnd | date | no |  |
| FeaturesJson | nvarchar(max) | no |  |
| ParamsJson | nvarchar(max) | no |  |
| MetricsJson | nvarchar(max) | no |  |
| ArtifactPath | nvarchar(400) | no |  |
| IsActive | bit | no |  |

## ml.Prediction

| columna | tipo | nulo | clave |
|---|---|---|---|
| PredictionID | bigint | no | PK |
| ModelVersion | nvarchar(50) | no |  FK?ml.ModelRegistry |
| SalesTerritory | nvarchar(50) | no |  |
| AsOfWeek | date | no |  |
| TargetWeekStart | date | no |  |
| HorizonWeeks | int | no |  |
| PredictedNetAmount | decimal(19,2) | no |  |
| PredictionDate | datetime2 | no |  |

## ops.Alert

| columna | tipo | nulo | clave |
|---|---|---|---|
| AlertID | int | no | PK |
| CreatedAt | datetime2 | no |  |
| AlertType | nvarchar(20) | no |  |
| Severity | nvarchar(10) | no |  |
| Indicator | nvarchar(100) | no |  |
| Entity | nvarchar(100) | no |  |
| ObservedValue | decimal(19,2) | sí |  |
| ThresholdValue | decimal(19,2) | sí |  |
| ReferenceValue | decimal(19,2) | sí |  |
| PeriodStart | date | sí |  |
| PeriodEnd | date | sí |  |
| Origin | nvarchar(100) | no |  |
| ModelVersion | nvarchar(50) | sí |  |
| Message | nvarchar(1000) | no |  |
| Explanation | nvarchar(max) | sí |  |
| ExplanationIsAIGenerated | bit | no |  |
| RecommendedAction | nvarchar(1000) | sí |  |
| Status | nvarchar(20) | no |  |
| IsSimulated | bit | no |  |
| DedupKey | nvarchar(300) | no |  |
| UpdatedAt | datetime2 | sí |  |

## ops.DataQualityResult

| columna | tipo | nulo | clave |
|---|---|---|---|
| ResultID | bigint | no | PK |
| ExecutionID | int | no |  |
| QualityDimension | nvarchar(30) | no |  |
| ObjectName | nvarchar(200) | no |  |
| RuleID | nvarchar(20) | no |  |
| Description | nvarchar(300) | no |  |
| MetricValue | decimal(18,4) | sí |  |
| Threshold | decimal(18,4) | sí |  |
| Passed | bit | no |  |
| MeasuredAt | datetime2 | no |  |

## ops.EtlExecution

| columna | tipo | nulo | clave |
|---|---|---|---|
| ExecutionID | int | no | PK |
| PipelineName | nvarchar(100) | no |  |
| Mode | nvarchar(20) | no |  |
| TriggeredBy | nvarchar(50) | no |  |
| StartTime | datetime2 | no |  |
| EndTime | datetime2 | sí |  |
| Status | nvarchar(20) | no |  |
| ErrorDetail | nvarchar(max) | sí |  |
| Attempt | int | no |  |

## ops.EtlStepLog

| columna | tipo | nulo | clave |
|---|---|---|---|
| StepLogID | bigint | no | PK |
| ExecutionID | int | no |  FK?ops.EtlExecution |
| StepName | nvarchar(100) | no |  |
| SourceObject | nvarchar(200) | sí |  |
| TargetObject | nvarchar(200) | sí |  |
| RowsRead | int | sí |  |
| RowsInserted | int | sí |  |
| RowsUpdated | int | sí |  |
| RowsRejected | int | sí |  |
| WatermarkStart | datetime2 | sí |  |
| WatermarkEnd | datetime2 | sí |  |
| StartTime | datetime2 | no |  |
| EndTime | datetime2 | sí |  |
| Status | nvarchar(20) | no |  |
| ErrorDetail | nvarchar(max) | sí |  |

## ops.NotificationDelivery

| columna | tipo | nulo | clave |
|---|---|---|---|
| DeliveryID | int | no | PK |
| AlertID | int | no |  FK?ops.Alert |
| Channel | nvarchar(20) | no |  |
| Recipient | nvarchar(200) | sí |  |
| Status | nvarchar(20) | no |  |
| Attempts | int | no |  |
| LastError | nvarchar(1000) | sí |  |
| Detail | nvarchar(400) | sí |  |
| CreatedAt | datetime2 | no |  |
| DeliveredAt | datetime2 | sí |  |

## ops.Reconciliation

| columna | tipo | nulo | clave |
|---|---|---|---|
| ReconID | bigint | no | PK |
| ExecutionID | int | no |  |
| Layer | nvarchar(30) | no |  |
| ObjectName | nvarchar(200) | no |  |
| RowCountValue | bigint | no |  |
| AmountValue | decimal(19,2) | sí |  |
| Notes | nvarchar(300) | sí |  |
| MeasuredAt | datetime2 | no |  |

## ops.Watermark

| columna | tipo | nulo | clave |
|---|---|---|---|
| SourceObject | nvarchar(200) | no | PK |
| WatermarkColumn | nvarchar(100) | no |  |
| WatermarkValue | datetime2 | no |  |
| ExecutionID | int | sí |  |
| UpdatedAt | datetime2 | no |  |

