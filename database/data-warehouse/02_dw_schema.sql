/* =====================================================================
   02_dw_schema.sql  (base WWI_DW)
   Esquemas:
     dw  : modelo dimensional (Star Schema) del proceso VENTAS FACTURADAS
     ops : auditoría ETL, watermarks, calidad, reconciliación, alertas
     ml  : registro de modelos, predicciones y backtest
     ai  : bitácora del asistente generativo
   GRANO de dw.FactSales: UNA FILA POR LÍNEA DE FACTURA (Sales.InvoiceLines).
   ===================================================================== */
USE WWI_DW;
GO
IF SCHEMA_ID('dw')  IS NULL EXEC('CREATE SCHEMA dw');
IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');
IF SCHEMA_ID('ml')  IS NULL EXEC('CREATE SCHEMA ml');
IF SCHEMA_ID('ai')  IS NULL EXEC('CREATE SCHEMA ai');
GO

/* ============================ DIMENSIONES ============================ */
IF OBJECT_ID('dw.DimDate') IS NULL
CREATE TABLE dw.DimDate (
    DateKey int NOT NULL PRIMARY KEY,           -- yyyymmdd
    [Date] date NOT NULL UNIQUE,
    [Day] tinyint NOT NULL, DayName nvarchar(15) NOT NULL, DayOfWeekIso tinyint NOT NULL,
    WeekStart date NOT NULL,                     -- lunes de la semana
    IsoWeek tinyint NOT NULL,
    [Month] tinyint NOT NULL, MonthName nvarchar(15) NOT NULL, YearMonth char(7) NOT NULL,
    [Quarter] tinyint NOT NULL, YearQuarter char(7) NOT NULL,
    [Year] smallint NOT NULL,
    IsWeekend bit NOT NULL);

IF OBJECT_ID('dw.DimGeography') IS NULL
CREATE TABLE dw.DimGeography (
    GeographyKey int IDENTITY(1,1) PRIMARY KEY,
    CityID int NOT NULL UNIQUE,                  -- clave natural
    City nvarchar(50) NOT NULL, StateProvinceCode nvarchar(5) NOT NULL, StateProvince nvarchar(50) NOT NULL,
    SalesTerritory nvarchar(50) NOT NULL, Country nvarchar(60) NOT NULL, Continent nvarchar(30) NOT NULL,
    Region nvarchar(30) NOT NULL, Subregion nvarchar(30) NOT NULL, Population bigint NULL,
    ExecutionID int NULL, UpdatedAt datetime2 NOT NULL DEFAULT SYSDATETIME());

/* SCD Tipo 2: cambios en Categoría, Grupo de compra o Ciudad de entrega crean versión nueva.
   SCD Tipo 1: nombre, límite de crédito, días de pago y retención de crédito se sobrescriben. */
IF OBJECT_ID('dw.DimCustomer') IS NULL
CREATE TABLE dw.DimCustomer (
    CustomerKey int IDENTITY(1,1) PRIMARY KEY,
    CustomerID int NOT NULL,                     -- clave natural
    CustomerName nvarchar(100) NOT NULL, BillToCustomerID int NULL,
    CustomerCategory nvarchar(50) NOT NULL, BuyingGroup nvarchar(50) NOT NULL,
    CityID int NULL, GeographyKey int NOT NULL,
    CreditLimit decimal(18,2) NULL, PaymentDays int NULL, IsOnCreditHold bit NULL,
    ValidFrom date NOT NULL, ValidTo date NOT NULL, IsCurrent bit NOT NULL,
    Scd2Hash varbinary(32) NOT NULL,
    ExecutionID int NULL, UpdatedAt datetime2 NOT NULL DEFAULT SYSDATETIME());

IF OBJECT_ID('dw.DimProduct') IS NULL
CREATE TABLE dw.DimProduct (
    ProductKey int IDENTITY(1,1) PRIMARY KEY,
    StockItemID int NOT NULL UNIQUE,             -- clave natural (SCD Tipo 1)
    ProductName nvarchar(100) NOT NULL, Category nvarchar(50) NOT NULL, AllCategories nvarchar(400) NOT NULL,
    Brand nvarchar(50) NOT NULL, Size nvarchar(20) NOT NULL, IsChillerStock bit NULL,
    ListUnitPrice decimal(18,2) NULL, RecommendedRetailPrice decimal(18,2) NULL,
    ExecutionID int NULL, UpdatedAt datetime2 NOT NULL DEFAULT SYSDATETIME());

IF OBJECT_ID('dw.DimEmployee') IS NULL
CREATE TABLE dw.DimEmployee (
    EmployeeKey int IDENTITY(1,1) PRIMARY KEY,
    EmployeeID int NOT NULL UNIQUE,              -- clave natural (SCD Tipo 1)
    EmployeeName nvarchar(50) NOT NULL, PreferredName nvarchar(50) NULL, Role nvarchar(20) NOT NULL,
    ExecutionID int NULL, UpdatedAt datetime2 NOT NULL DEFAULT SYSDATETIME());
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='UX_DimCustomer_Current')
    CREATE UNIQUE INDEX UX_DimCustomer_Current ON dw.DimCustomer(CustomerID) WHERE IsCurrent = 1;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_DimCustomer_NK')
    CREATE INDEX IX_DimCustomer_NK ON dw.DimCustomer(CustomerID, ValidFrom, ValidTo) INCLUDE (CustomerKey, GeographyKey);
GO

/* Miembros desconocidos (-1): política para hechos sin dimensión correspondiente. */
SET IDENTITY_INSERT dw.DimGeography ON;
IF NOT EXISTS (SELECT 1 FROM dw.DimGeography WHERE GeographyKey = -1)
    INSERT dw.DimGeography (GeographyKey, CityID, City, StateProvinceCode, StateProvince, SalesTerritory, Country, Continent, Region, Subregion)
    VALUES (-1, -1, 'Desconocido', '??', 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido');
SET IDENTITY_INSERT dw.DimGeography OFF;
SET IDENTITY_INSERT dw.DimCustomer ON;
IF NOT EXISTS (SELECT 1 FROM dw.DimCustomer WHERE CustomerKey = -1)
    INSERT dw.DimCustomer (CustomerKey, CustomerID, CustomerName, CustomerCategory, BuyingGroup, GeographyKey, ValidFrom, ValidTo, IsCurrent, Scd2Hash)
    VALUES (-1, -1, 'Desconocido', 'Desconocido', 'Desconocido', -1, '1900-01-01', '9999-12-31', 1, 0x00);
SET IDENTITY_INSERT dw.DimCustomer OFF;
SET IDENTITY_INSERT dw.DimProduct ON;
IF NOT EXISTS (SELECT 1 FROM dw.DimProduct WHERE ProductKey = -1)
    INSERT dw.DimProduct (ProductKey, StockItemID, ProductName, Category, AllCategories, Brand, Size)
    VALUES (-1, -1, 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido', 'N/A');
SET IDENTITY_INSERT dw.DimProduct OFF;
SET IDENTITY_INSERT dw.DimEmployee ON;
IF NOT EXISTS (SELECT 1 FROM dw.DimEmployee WHERE EmployeeKey = -1)
    INSERT dw.DimEmployee (EmployeeKey, EmployeeID, EmployeeName, Role) VALUES (-1, -1, 'Desconocido', 'Desconocido');
SET IDENTITY_INSERT dw.DimEmployee OFF;
GO

/* ============================== HECHOS =============================== */
IF OBJECT_ID('dw.FactSales') IS NULL
CREATE TABLE dw.FactSales (
    SalesKey bigint IDENTITY(1,1) PRIMARY KEY,
    InvoiceLineID int NOT NULL,                  -- clave natural del grano (degenerada)
    InvoiceID int NOT NULL,                      -- dimensión degenerada
    DateKey int NOT NULL REFERENCES dw.DimDate(DateKey),
    CustomerKey int NOT NULL REFERENCES dw.DimCustomer(CustomerKey),
    ProductKey int NOT NULL REFERENCES dw.DimProduct(ProductKey),
    EmployeeKey int NOT NULL REFERENCES dw.DimEmployee(EmployeeKey),
    GeographyKey int NOT NULL REFERENCES dw.DimGeography(GeographyKey),
    Quantity int NOT NULL,                       -- aditiva
    UnitPrice decimal(18,2) NOT NULL,            -- no aditiva (se promedia ponderada)
    TaxRate decimal(18,3) NOT NULL,              -- no aditiva
    NetAmount decimal(18,2) NOT NULL,            -- aditiva: Quantity * UnitPrice (sin impuesto)
    TaxAmount decimal(18,2) NOT NULL,            -- aditiva
    GrossAmount decimal(18,2) NOT NULL,          -- aditiva: ExtendedPrice (con impuesto)
    LineProfit decimal(18,2) NOT NULL,           -- aditiva
    IsUnitPriceDerived bit NOT NULL DEFAULT 0,   -- marca de imputación
    ExecutionID int NULL, LoadedAt datetime2 NOT NULL DEFAULT SYSDATETIME(), UpdatedAt datetime2 NULL,
    CONSTRAINT UX_FactSales_InvoiceLine UNIQUE (InvoiceLineID),
    CONSTRAINT CK_FactSales_Qty CHECK (Quantity > 0));
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_FactSales_Date')
    CREATE INDEX IX_FactSales_Date ON dw.FactSales(DateKey) INCLUDE (CustomerKey, ProductKey, GeographyKey, EmployeeKey, Quantity, NetAmount, LineProfit, InvoiceID);
GO

/* ======================= OPERACIÓN / AUDITORÍA ======================= */
IF OBJECT_ID('ops.EtlExecution') IS NULL
CREATE TABLE ops.EtlExecution (
    ExecutionID int IDENTITY(1,1) PRIMARY KEY,
    PipelineName nvarchar(100) NOT NULL, Mode nvarchar(20) NOT NULL,      -- initial | incremental
    TriggeredBy nvarchar(50) NOT NULL, StartTime datetime2 NOT NULL DEFAULT SYSDATETIME(), EndTime datetime2 NULL,
    Status nvarchar(20) NOT NULL DEFAULT 'running',                        -- running | success | failed
    ErrorDetail nvarchar(max) NULL, Attempt int NOT NULL DEFAULT 1);
IF OBJECT_ID('ops.EtlStepLog') IS NULL
CREATE TABLE ops.EtlStepLog (
    StepLogID bigint IDENTITY(1,1) PRIMARY KEY,
    ExecutionID int NOT NULL REFERENCES ops.EtlExecution(ExecutionID),
    StepName nvarchar(100) NOT NULL, SourceObject nvarchar(200) NULL, TargetObject nvarchar(200) NULL,
    RowsRead int NULL, RowsInserted int NULL, RowsUpdated int NULL, RowsRejected int NULL,
    WatermarkStart datetime2 NULL, WatermarkEnd datetime2 NULL,
    StartTime datetime2 NOT NULL, EndTime datetime2 NULL, Status nvarchar(20) NOT NULL, ErrorDetail nvarchar(max) NULL);
IF OBJECT_ID('ops.Watermark') IS NULL
CREATE TABLE ops.Watermark (
    SourceObject nvarchar(200) NOT NULL PRIMARY KEY, WatermarkColumn nvarchar(100) NOT NULL,
    WatermarkValue datetime2 NOT NULL, ExecutionID int NULL, UpdatedAt datetime2 NOT NULL DEFAULT SYSDATETIME());
IF OBJECT_ID('ops.DataQualityResult') IS NULL
CREATE TABLE ops.DataQualityResult (
    ResultID bigint IDENTITY(1,1) PRIMARY KEY, ExecutionID int NOT NULL,
    QualityDimension nvarchar(30) NOT NULL,      -- Completitud | Unicidad | Validez | Consistencia | Integridad | Oportunidad
    ObjectName nvarchar(200) NOT NULL, RuleID nvarchar(20) NOT NULL, Description nvarchar(300) NOT NULL,
    MetricValue decimal(18,4) NULL, Threshold decimal(18,4) NULL, Passed bit NOT NULL, MeasuredAt datetime2 NOT NULL DEFAULT SYSDATETIME());
IF OBJECT_ID('ops.Reconciliation') IS NULL
CREATE TABLE ops.Reconciliation (
    ReconID bigint IDENTITY(1,1) PRIMARY KEY, ExecutionID int NOT NULL,
    Layer nvarchar(30) NOT NULL, ObjectName nvarchar(200) NOT NULL,
    RowCountValue bigint NOT NULL, AmountValue decimal(19,2) NULL, Notes nvarchar(300) NULL,
    MeasuredAt datetime2 NOT NULL DEFAULT SYSDATETIME());

IF OBJECT_ID('ops.Alert') IS NULL
CREATE TABLE ops.Alert (
    AlertID int IDENTITY(1,1) PRIMARY KEY,
    CreatedAt datetime2 NOT NULL DEFAULT SYSDATETIME(),
    AlertType nvarchar(20) NOT NULL,             -- regla | ml | ia
    Severity nvarchar(10) NOT NULL,              -- baja | media | alta
    Indicator nvarchar(100) NOT NULL, Entity nvarchar(100) NOT NULL,
    ObservedValue decimal(19,2) NULL, ThresholdValue decimal(19,2) NULL, ReferenceValue decimal(19,2) NULL,
    PeriodStart date NULL, PeriodEnd date NULL,
    Origin nvarchar(100) NOT NULL,               -- regla R-ALR-01 / modelo vX / IA
    ModelVersion nvarchar(50) NULL,
    Message nvarchar(1000) NOT NULL,
    Explanation nvarchar(max) NULL, ExplanationIsAIGenerated bit NOT NULL DEFAULT 0,
    RecommendedAction nvarchar(1000) NULL,
    Status nvarchar(20) NOT NULL DEFAULT 'nueva', -- nueva | atendida | descartada | resuelta
    IsSimulated bit NOT NULL DEFAULT 0,
    DedupKey nvarchar(300) NOT NULL,
    UpdatedAt datetime2 NULL,
    CONSTRAINT UX_Alert_Dedup UNIQUE (DedupKey));
IF OBJECT_ID('ops.NotificationDelivery') IS NULL
CREATE TABLE ops.NotificationDelivery (
    DeliveryID int IDENTITY(1,1) PRIMARY KEY,
    AlertID int NOT NULL REFERENCES ops.Alert(AlertID),
    Channel nvarchar(20) NOT NULL,               -- web | email
    Recipient nvarchar(200) NULL, Status nvarchar(20) NOT NULL,   -- pendiente | entregado | fallido
    Attempts int NOT NULL DEFAULT 0, LastError nvarchar(1000) NULL, Detail nvarchar(400) NULL,
    CreatedAt datetime2 NOT NULL DEFAULT SYSDATETIME(), DeliveredAt datetime2 NULL,
    CONSTRAINT UX_Delivery UNIQUE (AlertID, Channel));

/* ================================ ML ================================= */
IF OBJECT_ID('ml.ModelRegistry') IS NULL
CREATE TABLE ml.ModelRegistry (
    ModelVersion nvarchar(50) NOT NULL PRIMARY KEY, ModelName nvarchar(100) NOT NULL, Algorithm nvarchar(100) NOT NULL,
    TrainedAt datetime2 NOT NULL DEFAULT SYSDATETIME(),
    TrainStart date NOT NULL, TrainEnd date NOT NULL, ValidStart date NOT NULL, ValidEnd date NOT NULL, TestStart date NOT NULL, TestEnd date NOT NULL,
    FeaturesJson nvarchar(max) NOT NULL, ParamsJson nvarchar(max) NOT NULL, MetricsJson nvarchar(max) NOT NULL,
    ArtifactPath nvarchar(400) NOT NULL, IsActive bit NOT NULL DEFAULT 0);
IF OBJECT_ID('ml.Prediction') IS NULL
CREATE TABLE ml.Prediction (
    PredictionID bigint IDENTITY(1,1) PRIMARY KEY,
    ModelVersion nvarchar(50) NOT NULL REFERENCES ml.ModelRegistry(ModelVersion),
    SalesTerritory nvarchar(50) NOT NULL, AsOfWeek date NOT NULL, TargetWeekStart date NOT NULL, HorizonWeeks int NOT NULL,
    PredictedNetAmount decimal(19,2) NOT NULL, PredictionDate datetime2 NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT UX_Prediction UNIQUE (ModelVersion, SalesTerritory, AsOfWeek, TargetWeekStart));
IF OBJECT_ID('ml.BacktestResult') IS NULL
CREATE TABLE ml.BacktestResult (
    ModelVersion nvarchar(50) NOT NULL, SalesTerritory nvarchar(50) NOT NULL, WeekStart date NOT NULL, SplitName nvarchar(10) NOT NULL,
    ActualNetAmount decimal(19,2) NOT NULL, PredictedNetAmount decimal(19,2) NOT NULL, BaselineNetAmount decimal(19,2) NOT NULL,
    CONSTRAINT PK_Backtest PRIMARY KEY (ModelVersion, SalesTerritory, WeekStart));

/* ================================ AI ================================= */
IF OBJECT_ID('ai.AssistantLog') IS NULL
CREATE TABLE ai.AssistantLog (
    LogID bigint IDENTITY(1,1) PRIMARY KEY, AskedAt datetime2 NOT NULL DEFAULT SYSDATETIME(),
    Username nvarchar(50) NOT NULL, Question nvarchar(600) NOT NULL, ToolsJson nvarchar(max) NULL,
    Status nvarchar(30) NOT NULL, AnswerChars int NULL, LatencyMs int NULL,
    InputTokens int NULL, OutputTokens int NULL, Model nvarchar(60) NULL, ErrorDetail nvarchar(1000) NULL);
GO

/* ===================== VISTA ANALÍTICA APROBADA ====================== */
/* Única superficie de lectura para la API/BI y el asistente generativo. */
CREATE OR ALTER VIEW dw.vw_SalesAnalytics AS
SELECT f.SalesKey, f.InvoiceLineID, f.InvoiceID,
       d.[Date] AS InvoiceDate, d.[Year], d.[Quarter], d.YearQuarter, d.[Month], d.YearMonth, d.WeekStart,
       c.CustomerID, c.CustomerName, c.CustomerCategory, c.BuyingGroup,
       g.City, g.StateProvince, g.SalesTerritory, g.Country,
       p.StockItemID, p.ProductName, p.Category, p.Brand,
       e.EmployeeName AS Salesperson,
       f.Quantity, f.UnitPrice, f.NetAmount, f.TaxAmount, f.GrossAmount, f.LineProfit
FROM dw.FactSales f
JOIN dw.DimDate d      ON d.DateKey = f.DateKey
JOIN dw.DimCustomer c  ON c.CustomerKey = f.CustomerKey
JOIN dw.DimGeography g ON g.GeographyKey = f.GeographyKey
JOIN dw.DimProduct p   ON p.ProductKey = f.ProductKey
JOIN dw.DimEmployee e  ON e.EmployeeKey = f.EmployeeKey;
GO
CREATE OR ALTER VIEW ops.vw_PipelineStatus AS
SELECT TOP (1) e.ExecutionID, e.PipelineName, e.Mode, e.StartTime, e.EndTime, e.Status,
       DATEDIFF(SECOND, e.StartTime, e.EndTime) AS DurationSec
FROM ops.EtlExecution e WHERE e.Status = 'success' ORDER BY e.EndTime DESC;
GO
