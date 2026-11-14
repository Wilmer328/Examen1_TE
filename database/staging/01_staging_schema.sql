/* =====================================================================
   01_staging_schema.sql  (base WWI_Staging)
   Zonas:
     raw        : Landing. Copia fiel de lo extraído, APPEND-ONLY (nunca se
                  sobrescribe). Cada fila lleva _execution_id y _extracted_at.
     clean      : Datos validados/estandarizados. Una fila por clave de negocio
                  (estado vigente), cargada con MERGE (upsert idempotente).
     quarantine : Registros rechazados por reglas de calidad, con regla y detalle.
     ready      : Vistas de integración listas para el DW (claves de negocio + linaje).
   ===================================================================== */
USE WWI_Staging;
GO
IF SCHEMA_ID('raw') IS NULL EXEC('CREATE SCHEMA raw');
IF SCHEMA_ID('clean') IS NULL EXEC('CREATE SCHEMA clean');
IF SCHEMA_ID('quarantine') IS NULL EXEC('CREATE SCHEMA quarantine');
IF SCHEMA_ID('ready') IS NULL EXEC('CREATE SCHEMA ready');
GO

/* ----------------------------- RAW ---------------------------------- */
IF OBJECT_ID('raw.Countries') IS NULL
CREATE TABLE raw.Countries (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    CountryID int, CountryName nvarchar(60), Continent nvarchar(30), Region nvarchar(30), Subregion nvarchar(30), ValidFrom datetime2);
IF OBJECT_ID('raw.StateProvinces') IS NULL
CREATE TABLE raw.StateProvinces (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    StateProvinceID int, StateProvinceCode nvarchar(5), StateProvinceName nvarchar(50), CountryID int, SalesTerritory nvarchar(50), ValidFrom datetime2);
IF OBJECT_ID('raw.Cities') IS NULL
CREATE TABLE raw.Cities (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    CityID int, CityName nvarchar(50), StateProvinceID int, LatestRecordedPopulation bigint, ValidFrom datetime2);
IF OBJECT_ID('raw.People') IS NULL
CREATE TABLE raw.People (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    PersonID int, FullName nvarchar(50), PreferredName nvarchar(50), IsEmployee bit, IsSalesperson bit, ValidFrom datetime2);
IF OBJECT_ID('raw.CustomerCategories') IS NULL
CREATE TABLE raw.CustomerCategories (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    CustomerCategoryID int, CustomerCategoryName nvarchar(50), ValidFrom datetime2);
IF OBJECT_ID('raw.BuyingGroups') IS NULL
CREATE TABLE raw.BuyingGroups (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    BuyingGroupID int, BuyingGroupName nvarchar(50), ValidFrom datetime2);
IF OBJECT_ID('raw.Customers') IS NULL
CREATE TABLE raw.Customers (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    CustomerID int, CustomerName nvarchar(100), BillToCustomerID int, CustomerCategoryID int, BuyingGroupID int,
    DeliveryCityID int, CreditLimit decimal(18,2), AccountOpenedDate date, StandardDiscountPercentage decimal(18,3),
    IsOnCreditHold bit, PaymentDays int, ValidFrom datetime2);
IF OBJECT_ID('raw.StockGroups') IS NULL
CREATE TABLE raw.StockGroups (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    StockGroupID int, StockGroupName nvarchar(50), ValidFrom datetime2);
IF OBJECT_ID('raw.StockItemStockGroups') IS NULL
CREATE TABLE raw.StockItemStockGroups (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    StockItemStockGroupID int, StockItemID int, StockGroupID int, LastEditedWhen datetime2);
IF OBJECT_ID('raw.StockItems') IS NULL
CREATE TABLE raw.StockItems (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    StockItemID int, StockItemName nvarchar(100), Brand nvarchar(50), Size nvarchar(20), IsChillerStock bit,
    TaxRate decimal(18,3), UnitPrice decimal(18,2), RecommendedRetailPrice decimal(18,2), ValidFrom datetime2);
IF OBJECT_ID('raw.Invoices') IS NULL
CREATE TABLE raw.Invoices (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    InvoiceID int, CustomerID int, BillToCustomerID int, OrderID int, SalespersonPersonID int, InvoiceDate date,
    IsCreditNote bit, LastEditedWhen datetime2);
IF OBJECT_ID('raw.InvoiceLines') IS NULL
CREATE TABLE raw.InvoiceLines (
    _raw_id bigint IDENTITY PRIMARY KEY, _execution_id int NOT NULL, _extracted_at datetime2 NOT NULL DEFAULT SYSDATETIME(),
    InvoiceLineID int, InvoiceID int, StockItemID int, Description nvarchar(100), Quantity int, UnitPrice decimal(18,2),
    TaxRate decimal(18,3), TaxAmount decimal(18,2), LineProfit decimal(18,2), ExtendedPrice decimal(18,2), LastEditedWhen datetime2);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_raw_InvoiceLines_exec')
    CREATE INDEX IX_raw_InvoiceLines_exec ON raw.InvoiceLines(_execution_id, InvoiceLineID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_raw_Invoices_exec')
    CREATE INDEX IX_raw_Invoices_exec ON raw.Invoices(_execution_id, InvoiceID);
GO

/* ----------------------------- CLEAN -------------------------------- */
IF OBJECT_ID('clean.Countries') IS NULL
CREATE TABLE clean.Countries (CountryID int PRIMARY KEY, CountryName nvarchar(60) NOT NULL, Continent nvarchar(30), Region nvarchar(30),
    Subregion nvarchar(30), ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.StateProvinces') IS NULL
CREATE TABLE clean.StateProvinces (StateProvinceID int PRIMARY KEY, StateProvinceCode nvarchar(5), StateProvinceName nvarchar(50) NOT NULL,
    CountryID int, SalesTerritory nvarchar(50) NOT NULL, ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.Cities') IS NULL
CREATE TABLE clean.Cities (CityID int PRIMARY KEY, CityName nvarchar(50) NOT NULL, StateProvinceID int, LatestRecordedPopulation bigint,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.People') IS NULL
CREATE TABLE clean.People (PersonID int PRIMARY KEY, FullName nvarchar(50) NOT NULL, PreferredName nvarchar(50), IsEmployee bit, IsSalesperson bit,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.CustomerCategories') IS NULL
CREATE TABLE clean.CustomerCategories (CustomerCategoryID int PRIMARY KEY, CustomerCategoryName nvarchar(50) NOT NULL,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.BuyingGroups') IS NULL
CREATE TABLE clean.BuyingGroups (BuyingGroupID int PRIMARY KEY, BuyingGroupName nvarchar(50) NOT NULL,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.Customers') IS NULL
CREATE TABLE clean.Customers (CustomerID int PRIMARY KEY, CustomerName nvarchar(100) NOT NULL, BillToCustomerID int, CustomerCategoryID int,
    BuyingGroupID int NULL, DeliveryCityID int, CreditLimit decimal(18,2) NULL, AccountOpenedDate date, StandardDiscountPercentage decimal(18,3),
    IsOnCreditHold bit, PaymentDays int, ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.StockGroups') IS NULL
CREATE TABLE clean.StockGroups (StockGroupID int PRIMARY KEY, StockGroupName nvarchar(50) NOT NULL,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.StockItemStockGroups') IS NULL
CREATE TABLE clean.StockItemStockGroups (StockItemStockGroupID int PRIMARY KEY, StockItemID int NOT NULL, StockGroupID int NOT NULL,
    LastEditedWhen datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.StockItems') IS NULL
CREATE TABLE clean.StockItems (StockItemID int PRIMARY KEY, StockItemName nvarchar(100) NOT NULL, Brand nvarchar(50) NOT NULL, Size nvarchar(20) NOT NULL,
    IsChillerStock bit, TaxRate decimal(18,3), UnitPrice decimal(18,2), RecommendedRetailPrice decimal(18,2) NULL,
    ValidFrom datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.Invoices') IS NULL
CREATE TABLE clean.Invoices (InvoiceID int PRIMARY KEY, CustomerID int NOT NULL, BillToCustomerID int, OrderID int NULL,
    SalespersonPersonID int, InvoiceDate date NOT NULL, IsCreditNote bit, LastEditedWhen datetime2,
    _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
IF OBJECT_ID('clean.InvoiceLines') IS NULL
CREATE TABLE clean.InvoiceLines (InvoiceLineID int PRIMARY KEY, InvoiceID int NOT NULL, StockItemID int NOT NULL, Description nvarchar(100),
    Quantity int NOT NULL, UnitPrice decimal(18,2) NOT NULL, TaxRate decimal(18,3), TaxAmount decimal(18,2), LineProfit decimal(18,2),
    ExtendedPrice decimal(18,2), IsUnitPriceDerived bit NOT NULL DEFAULT 0, IsQuantityOutlier bit NOT NULL DEFAULT 0,
    LastEditedWhen datetime2, _execution_id int, _updated_at datetime2 DEFAULT SYSDATETIME());
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_clean_InvoiceLines_Invoice')
    CREATE INDEX IX_clean_InvoiceLines_Invoice ON clean.InvoiceLines(InvoiceID);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_clean_InvoiceLines_exec')
    CREATE INDEX IX_clean_InvoiceLines_exec ON clean.InvoiceLines(_execution_id);
GO

/* Parámetros de calidad persistidos (p. ej. umbral estadístico de outliers calculado una vez en la
   carga inicial). Persistirlo hace la marca determinista y evita recalcular sobre todo el histórico. */
IF OBJECT_ID('clean.QualityParameter') IS NULL
CREATE TABLE clean.QualityParameter (
    ParameterName nvarchar(100) PRIMARY KEY, ParameterValue decimal(18,4) NOT NULL,
    Method nvarchar(300) NOT NULL, ComputedAt datetime2 NOT NULL DEFAULT SYSDATETIME(), ExecutionID int NULL);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_raw_InvoiceLines_key')
    CREATE INDEX IX_raw_InvoiceLines_key ON raw.InvoiceLines(InvoiceLineID, _raw_id);
GO

/* --------------------------- QUARANTINE ----------------------------- */
IF OBJECT_ID('quarantine.RejectedRecord') IS NULL
CREATE TABLE quarantine.RejectedRecord (
    RejectedID bigint IDENTITY PRIMARY KEY,
    ExecutionID int NOT NULL,
    SourceObject nvarchar(100) NOT NULL,
    BusinessKey nvarchar(100) NOT NULL,
    RuleID nvarchar(20) NOT NULL,
    RuleDescription nvarchar(300) NOT NULL,
    Detail nvarchar(1000) NULL,
    RecordJson nvarchar(max) NULL,
    RejectedAt datetime2 NOT NULL DEFAULT SYSDATETIME(),
    Status nvarchar(20) NOT NULL DEFAULT 'pendiente');   -- pendiente | reprocesado | descartado
GO

/* ----------------------------- READY -------------------------------- */
/* Cliente integrado: categoría, grupo de compra y geografía de entrega.
   Nulos "No aplica": BuyingGroupID NULL -> 'Sin grupo de compra'. */
CREATE OR ALTER VIEW ready.vw_Customer AS
SELECT c.CustomerID,
       c.CustomerName,
       c.BillToCustomerID,
       ISNULL(cc.CustomerCategoryName, 'Desconocido')          AS CustomerCategory,
       CASE WHEN c.BuyingGroupID IS NULL THEN 'Sin grupo de compra'
            ELSE ISNULL(bg.BuyingGroupName, 'Desconocido') END AS BuyingGroup,
       c.DeliveryCityID                                         AS CityID,
       c.CreditLimit,
       c.PaymentDays,
       c.IsOnCreditHold,
       c.AccountOpenedDate,
       'WideWorldImporters.Sales.Customers'                     AS _lineage_source,
       c._execution_id
FROM clean.Customers c
LEFT JOIN clean.CustomerCategories cc ON cc.CustomerCategoryID = c.CustomerCategoryID
LEFT JOIN clean.BuyingGroups bg       ON bg.BuyingGroupID = c.BuyingGroupID;
GO
CREATE OR ALTER VIEW ready.vw_Geography AS
SELECT ci.CityID, ci.CityName, sp.StateProvinceCode, sp.StateProvinceName, sp.SalesTerritory,
       co.CountryName, co.Continent, co.Region, co.Subregion, ci.LatestRecordedPopulation
FROM clean.Cities ci
JOIN clean.StateProvinces sp ON sp.StateProvinceID = ci.StateProvinceID
JOIN clean.Countries co      ON co.CountryID = sp.CountryID;
GO
/* Producto: un artículo puede pertenecer a varios StockGroups (relación N:M).
   Para NO multiplicar medidas, se asigna UNA categoría principal = grupo con
   menor StockGroupID (regla documentada) y se conserva la lista completa como texto. */
CREATE OR ALTER VIEW ready.vw_Product AS
WITH g AS (
    SELECT sisg.StockItemID, sg.StockGroupID, sg.StockGroupName,
           ROW_NUMBER() OVER (PARTITION BY sisg.StockItemID ORDER BY sg.StockGroupID) AS rn
    FROM clean.StockItemStockGroups sisg
    JOIN clean.StockGroups sg ON sg.StockGroupID = sisg.StockGroupID
)
SELECT si.StockItemID, si.StockItemName, si.Brand, si.Size, si.IsChillerStock, si.UnitPrice AS ListUnitPrice,
       si.RecommendedRetailPrice, si.TaxRate,
       ISNULL(gp.StockGroupName, 'Desconocido') AS Category,
       ISNULL((SELECT STRING_AGG(g2.StockGroupName, ', ') WITHIN GROUP (ORDER BY g2.StockGroupID)
               FROM g g2 WHERE g2.StockItemID = si.StockItemID), 'Desconocido') AS AllCategories
FROM clean.StockItems si
LEFT JOIN g gp ON gp.StockItemID = si.StockItemID AND gp.rn = 1;
GO
CREATE OR ALTER VIEW ready.vw_Employee AS
SELECT PersonID AS EmployeeID, FullName, PreferredName,
       CASE WHEN IsSalesperson = 1 THEN 'Vendedor' WHEN IsEmployee = 1 THEN 'Empleado' ELSE 'Externo' END AS Role
FROM clean.People
WHERE IsEmployee = 1;
GO
/* Línea de venta integrada (grano = línea de factura). Join 1:1 línea->cabecera. */
CREATE OR ALTER VIEW ready.vw_SalesLine AS
SELECT il.InvoiceLineID, il.InvoiceID, i.InvoiceDate, i.CustomerID, i.BillToCustomerID, i.SalespersonPersonID,
       il.StockItemID, il.Description, il.Quantity, il.UnitPrice, il.TaxRate, il.TaxAmount, il.LineProfit,
       il.ExtendedPrice, il.IsUnitPriceDerived, il.IsQuantityOutlier,
       CASE WHEN i.LastEditedWhen > il.LastEditedWhen THEN i.LastEditedWhen ELSE il.LastEditedWhen END AS SourceLastEdited,
       il._execution_id, i._execution_id AS _header_execution_id
FROM clean.InvoiceLines il
JOIN clean.Invoices i ON i.InvoiceID = il.InvoiceID;
GO
