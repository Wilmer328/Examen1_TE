/* =====================================================================
   03_dw_load_procs.sql  (base WWI_DW)
   Procedimientos de carga dimensional. Todos son IDEMPOTENTES:
   re-ejecutarlos con los mismos datos no inserta ni modifica filas.
   Cada procedimiento devuelve un result set: inserted, updated.
   ===================================================================== */
USE WWI_DW;
GO

/* ---------------------------- DimDate ------------------------------- */
CREATE OR ALTER PROCEDURE dw.usp_LoadDimDate @From date = '2013-01-01', @To date = '2026-12-31'
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH n AS (SELECT TOP (DATEDIFF(DAY, @From, @To) + 1)
                       DATEADD(DAY, ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1, @From) AS d
                FROM sys.all_objects a CROSS JOIN sys.all_objects b),
          x AS (SELECT d, (DATEDIFF(DAY, '19000101', d) % 7) + 1 AS iso FROM n)
    INSERT dw.DimDate (DateKey, [Date], [Day], DayName, DayOfWeekIso, WeekStart, IsoWeek, [Month], MonthName, YearMonth,
                       [Quarter], YearQuarter, [Year], IsWeekend)
    SELECT YEAR(d) * 10000 + MONTH(d) * 100 + DAY(d), d, DAY(d),
           CHOOSE(iso, N'Lunes', N'Martes', N'Miércoles', N'Jueves', N'Viernes', N'Sábado', N'Domingo'), iso,
           DATEADD(DAY, 1 - iso, d), DATEPART(ISO_WEEK, d), MONTH(d),
           CHOOSE(MONTH(d), N'Enero', N'Febrero', N'Marzo', N'Abril', N'Mayo', N'Junio', N'Julio', N'Agosto',
                  N'Septiembre', N'Octubre', N'Noviembre', N'Diciembre'),
           CONVERT(char(7), d, 126), DATEPART(QUARTER, d),
           CONCAT(YEAR(d), '-Q', DATEPART(QUARTER, d)), YEAR(d), IIF(iso >= 6, 1, 0)
    FROM x
    WHERE NOT EXISTS (SELECT 1 FROM dw.DimDate t WHERE t.[Date] = x.d);
    SELECT @@ROWCOUNT AS inserted, 0 AS updated;
END
GO

/* -------------------------- DimGeography (SCD1) --------------------- */
CREATE OR ALTER PROCEDURE dw.usp_LoadDimGeography @ExecutionID int
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @a TABLE (act nvarchar(10));
    MERGE dw.DimGeography AS t
    USING (SELECT CityID, CityName, StateProvinceCode, StateProvinceName, SalesTerritory, CountryName,
                  Continent, Region, Subregion, LatestRecordedPopulation
           FROM WWI_Staging.ready.vw_Geography) AS s
    ON t.CityID = s.CityID
    WHEN MATCHED AND EXISTS (SELECT s.CityName, s.StateProvinceCode, s.StateProvinceName, s.SalesTerritory, s.CountryName,
                                    s.Continent, s.Region, s.Subregion, s.LatestRecordedPopulation
                             EXCEPT
                             SELECT t.City, t.StateProvinceCode, t.StateProvince, t.SalesTerritory, t.Country,
                                    t.Continent, t.Region, t.Subregion, t.Population)
        THEN UPDATE SET City = s.CityName, StateProvinceCode = s.StateProvinceCode, StateProvince = s.StateProvinceName,
                        SalesTerritory = s.SalesTerritory, Country = s.CountryName, Continent = s.Continent, Region = s.Region,
                        Subregion = s.Subregion, Population = s.LatestRecordedPopulation, ExecutionID = @ExecutionID,
                        UpdatedAt = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET
        THEN INSERT (CityID, City, StateProvinceCode, StateProvince, SalesTerritory, Country, Continent, Region, Subregion, Population, ExecutionID)
             VALUES (s.CityID, s.CityName, s.StateProvinceCode, s.StateProvinceName, s.SalesTerritory, s.CountryName,
                     s.Continent, s.Region, s.Subregion, s.LatestRecordedPopulation, @ExecutionID)
    OUTPUT $action INTO @a;
    SELECT SUM(IIF(act = 'INSERT', 1, 0)) AS inserted, SUM(IIF(act = 'UPDATE', 1, 0)) AS updated FROM @a;
END
GO

/* ---------------------- DimCustomer (SCD1 + SCD2) ------------------- */
CREATE OR ALTER PROCEDURE dw.usp_LoadDimCustomer @ExecutionID int, @EffectiveDate date = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @EffectiveDate = ISNULL(@EffectiveDate, CAST(SYSDATETIME() AS date));
    DECLARE @ins int = 0, @upd int = 0, @n int;

    SELECT c.CustomerID, c.CustomerName, c.BillToCustomerID, c.CustomerCategory, c.BuyingGroup, c.CityID,
           ISNULL(g.GeographyKey, -1) AS GeographyKey, c.CreditLimit, c.PaymentDays, c.IsOnCreditHold,
           HASHBYTES('SHA2_256', CONCAT_WS('|', c.CustomerCategory, c.BuyingGroup, c.CityID)) AS Scd2Hash
    INTO #src
    FROM WWI_Staging.ready.vw_Customer c
    LEFT JOIN dw.DimGeography g ON g.CityID = c.CityID;

    BEGIN TRAN;
    -- 1) Clientes nuevos: primera versión vigente desde 1900-01-01
    INSERT dw.DimCustomer (CustomerID, CustomerName, BillToCustomerID, CustomerCategory, BuyingGroup, CityID, GeographyKey,
                           CreditLimit, PaymentDays, IsOnCreditHold, ValidFrom, ValidTo, IsCurrent, Scd2Hash, ExecutionID)
    SELECT s.CustomerID, s.CustomerName, s.BillToCustomerID, s.CustomerCategory, s.BuyingGroup, s.CityID, s.GeographyKey,
           s.CreditLimit, s.PaymentDays, s.IsOnCreditHold, '1900-01-01', '9999-12-31', 1, s.Scd2Hash, @ExecutionID
    FROM #src s
    WHERE NOT EXISTS (SELECT 1 FROM dw.DimCustomer d WHERE d.CustomerID = s.CustomerID);
    SET @ins += @@ROWCOUNT;

    -- 2) SCD2: cambio de atributos históricos.
    --    Si la versión vigente empezó hoy, se corrige en sitio (evita versiones de duración cero).
    UPDATE d SET CustomerCategory = s.CustomerCategory, BuyingGroup = s.BuyingGroup, CityID = s.CityID,
                 GeographyKey = s.GeographyKey, Scd2Hash = s.Scd2Hash, ExecutionID = @ExecutionID, UpdatedAt = SYSDATETIME()
    FROM dw.DimCustomer d JOIN #src s ON s.CustomerID = d.CustomerID
    WHERE d.IsCurrent = 1 AND d.Scd2Hash <> s.Scd2Hash AND d.ValidFrom = @EffectiveDate;
    SET @upd += @@ROWCOUNT;

    SELECT s.* INTO #changed
    FROM #src s JOIN dw.DimCustomer d ON d.CustomerID = s.CustomerID AND d.IsCurrent = 1
    WHERE d.Scd2Hash <> s.Scd2Hash;

    UPDATE d SET ValidTo = @EffectiveDate, IsCurrent = 0, UpdatedAt = SYSDATETIME()
    FROM dw.DimCustomer d JOIN #changed s ON s.CustomerID = d.CustomerID
    WHERE d.IsCurrent = 1;
    SET @upd += @@ROWCOUNT;

    INSERT dw.DimCustomer (CustomerID, CustomerName, BillToCustomerID, CustomerCategory, BuyingGroup, CityID, GeographyKey,
                           CreditLimit, PaymentDays, IsOnCreditHold, ValidFrom, ValidTo, IsCurrent, Scd2Hash, ExecutionID)
    SELECT CustomerID, CustomerName, BillToCustomerID, CustomerCategory, BuyingGroup, CityID, GeographyKey,
           CreditLimit, PaymentDays, IsOnCreditHold, @EffectiveDate, '9999-12-31', 1, Scd2Hash, @ExecutionID
    FROM #changed;
    SET @ins += @@ROWCOUNT;

    -- 3) SCD1: atributos que se sobrescriben en TODAS las versiones del cliente
    UPDATE d SET CustomerName = s.CustomerName, BillToCustomerID = s.BillToCustomerID, CreditLimit = s.CreditLimit,
                 PaymentDays = s.PaymentDays, IsOnCreditHold = s.IsOnCreditHold, ExecutionID = @ExecutionID, UpdatedAt = SYSDATETIME()
    FROM dw.DimCustomer d JOIN #src s ON s.CustomerID = d.CustomerID
    WHERE EXISTS (SELECT s.CustomerName, s.BillToCustomerID, s.CreditLimit, s.PaymentDays, s.IsOnCreditHold
                  EXCEPT SELECT d.CustomerName, d.BillToCustomerID, d.CreditLimit, d.PaymentDays, d.IsOnCreditHold);
    SET @upd += @@ROWCOUNT;
    COMMIT;

    SELECT @ins AS inserted, @upd AS updated;
END
GO

/* --------------------------- DimProduct (SCD1) ---------------------- */
CREATE OR ALTER PROCEDURE dw.usp_LoadDimProduct @ExecutionID int
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @a TABLE (act nvarchar(10));
    MERGE dw.DimProduct AS t
    USING WWI_Staging.ready.vw_Product AS s ON t.StockItemID = s.StockItemID
    WHEN MATCHED AND EXISTS (SELECT s.StockItemName, s.Category, s.AllCategories, s.Brand, s.Size, s.IsChillerStock, s.ListUnitPrice, s.RecommendedRetailPrice
                             EXCEPT SELECT t.ProductName, t.Category, t.AllCategories, t.Brand, t.Size, t.IsChillerStock, t.ListUnitPrice, t.RecommendedRetailPrice)
        THEN UPDATE SET ProductName = s.StockItemName, Category = s.Category, AllCategories = s.AllCategories, Brand = s.Brand,
                        Size = s.Size, IsChillerStock = s.IsChillerStock, ListUnitPrice = s.ListUnitPrice,
                        RecommendedRetailPrice = s.RecommendedRetailPrice, ExecutionID = @ExecutionID, UpdatedAt = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET
        THEN INSERT (StockItemID, ProductName, Category, AllCategories, Brand, Size, IsChillerStock, ListUnitPrice, RecommendedRetailPrice, ExecutionID)
             VALUES (s.StockItemID, s.StockItemName, s.Category, s.AllCategories, s.Brand, s.Size, s.IsChillerStock, s.ListUnitPrice,
                     s.RecommendedRetailPrice, @ExecutionID)
    OUTPUT $action INTO @a;
    SELECT SUM(IIF(act = 'INSERT', 1, 0)) AS inserted, SUM(IIF(act = 'UPDATE', 1, 0)) AS updated FROM @a;
END
GO

/* -------------------------- DimEmployee (SCD1) ---------------------- */
CREATE OR ALTER PROCEDURE dw.usp_LoadDimEmployee @ExecutionID int
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @a TABLE (act nvarchar(10));
    MERGE dw.DimEmployee AS t
    USING WWI_Staging.ready.vw_Employee AS s ON t.EmployeeID = s.EmployeeID
    WHEN MATCHED AND EXISTS (SELECT s.FullName, s.PreferredName, s.Role EXCEPT SELECT t.EmployeeName, t.PreferredName, t.Role)
        THEN UPDATE SET EmployeeName = s.FullName, PreferredName = s.PreferredName, Role = s.Role,
                        ExecutionID = @ExecutionID, UpdatedAt = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET
        THEN INSERT (EmployeeID, EmployeeName, PreferredName, Role, ExecutionID)
             VALUES (s.EmployeeID, s.FullName, s.PreferredName, s.Role, @ExecutionID)
    OUTPUT $action INTO @a;
    SELECT SUM(IIF(act = 'INSERT', 1, 0)) AS inserted, SUM(IIF(act = 'UPDATE', 1, 0)) AS updated FROM @a;
END
GO

/* ------------------------------ FactSales --------------------------- */
/* Resuelve claves sustitutas ANTES de insertar. Cliente con lookup por vigencia
   SCD2 (InvoiceDate dentro de [ValidFrom, ValidTo)). Sin dimensión -> -1.
   Incluye filas ya cargadas con miembro desconocido para corregir dimensiones tardías. */
CREATE OR ALTER PROCEDURE dw.usp_LoadFactSales @ExecutionID int, @FullReload bit = 0
AS
BEGIN
    SET NOCOUNT ON;
    SELECT s.InvoiceLineID, s.InvoiceID,
           YEAR(s.InvoiceDate) * 10000 + MONTH(s.InvoiceDate) * 100 + DAY(s.InvoiceDate) AS DateKey,
           ISNULL(c.CustomerKey, -1) AS CustomerKey,
           ISNULL(p.ProductKey, -1) AS ProductKey,
           ISNULL(e.EmployeeKey, -1) AS EmployeeKey,
           ISNULL(c.GeographyKey, -1) AS GeographyKey,
           s.Quantity, s.UnitPrice, s.TaxRate,
           CAST(s.ExtendedPrice - s.TaxAmount AS decimal(18,2)) AS NetAmount,
           s.TaxAmount, s.ExtendedPrice AS GrossAmount, s.LineProfit, s.IsUnitPriceDerived
    INTO #src
    FROM WWI_Staging.ready.vw_SalesLine s
    OUTER APPLY (SELECT TOP (1) dc.CustomerKey, dc.GeographyKey FROM dw.DimCustomer dc
                 WHERE dc.CustomerID = s.CustomerID AND s.InvoiceDate >= dc.ValidFrom AND s.InvoiceDate < dc.ValidTo
                 ORDER BY dc.ValidFrom DESC) c
    LEFT JOIN dw.DimProduct p  ON p.StockItemID = s.StockItemID
    LEFT JOIN dw.DimEmployee e ON e.EmployeeID = s.SalespersonPersonID
    WHERE @FullReload = 1
       OR s._execution_id = @ExecutionID
       OR s._header_execution_id = @ExecutionID
       OR s.InvoiceLineID IN (SELECT InvoiceLineID FROM dw.FactSales
                              WHERE CustomerKey = -1 OR ProductKey = -1 OR EmployeeKey = -1 OR GeographyKey = -1);

    DECLARE @a TABLE (act nvarchar(10));
    MERGE dw.FactSales AS t
    USING #src AS s ON t.InvoiceLineID = s.InvoiceLineID
    WHEN MATCHED AND EXISTS (SELECT s.InvoiceID, s.DateKey, s.CustomerKey, s.ProductKey, s.EmployeeKey, s.GeographyKey, s.Quantity,
                                    s.UnitPrice, s.TaxRate, s.NetAmount, s.TaxAmount, s.GrossAmount, s.LineProfit, s.IsUnitPriceDerived
                             EXCEPT
                             SELECT t.InvoiceID, t.DateKey, t.CustomerKey, t.ProductKey, t.EmployeeKey, t.GeographyKey, t.Quantity,
                                    t.UnitPrice, t.TaxRate, t.NetAmount, t.TaxAmount, t.GrossAmount, t.LineProfit, t.IsUnitPriceDerived)
        THEN UPDATE SET InvoiceID = s.InvoiceID, DateKey = s.DateKey, CustomerKey = s.CustomerKey, ProductKey = s.ProductKey,
                        EmployeeKey = s.EmployeeKey, GeographyKey = s.GeographyKey, Quantity = s.Quantity, UnitPrice = s.UnitPrice,
                        TaxRate = s.TaxRate, NetAmount = s.NetAmount, TaxAmount = s.TaxAmount, GrossAmount = s.GrossAmount,
                        LineProfit = s.LineProfit, IsUnitPriceDerived = s.IsUnitPriceDerived, ExecutionID = @ExecutionID,
                        UpdatedAt = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET
        THEN INSERT (InvoiceLineID, InvoiceID, DateKey, CustomerKey, ProductKey, EmployeeKey, GeographyKey, Quantity, UnitPrice,
                     TaxRate, NetAmount, TaxAmount, GrossAmount, LineProfit, IsUnitPriceDerived, ExecutionID)
             VALUES (s.InvoiceLineID, s.InvoiceID, s.DateKey, s.CustomerKey, s.ProductKey, s.EmployeeKey, s.GeographyKey, s.Quantity,
                     s.UnitPrice, s.TaxRate, s.NetAmount, s.TaxAmount, s.GrossAmount, s.LineProfit, s.IsUnitPriceDerived, @ExecutionID)
    OUTPUT $action INTO @a;
    SELECT ISNULL(SUM(IIF(act = 'INSERT', 1, 0)), 0) AS inserted, ISNULL(SUM(IIF(act = 'UPDATE', 1, 0)), 0) AS updated,
           (SELECT COUNT(*) FROM #src) AS rows_read FROM @a;
END
GO

/* --------------------------- Reconciliación -------------------------- */
/* Compara conteos y montos netos entre capas: fuente -> raw -> clean -> cuarentena -> DW.
   Regla esperada: fuente = clean + cuarentena_pendiente ; clean = DW. */
CREATE OR ALTER PROCEDURE ops.usp_Reconcile @ExecutionID int
AS
BEGIN
    SET NOCOUNT ON;
    INSERT ops.Reconciliation (ExecutionID, Layer, ObjectName, RowCountValue, AmountValue, Notes)
    SELECT @ExecutionID, '1-fuente', 'WideWorldImporters.Sales.InvoiceLines', COUNT_BIG(*), SUM(ExtendedPrice - TaxAmount), 'Neto = ExtendedPrice - TaxAmount'
    FROM WideWorldImporters.Sales.InvoiceLines
    UNION ALL
    SELECT @ExecutionID, '2-raw', 'WWI_Staging.raw.InvoiceLines (claves distintas)', COUNT_BIG(DISTINCT InvoiceLineID), NULL, 'Raw es append-only: se cuentan claves distintas'
    FROM WWI_Staging.raw.InvoiceLines
    UNION ALL
    SELECT @ExecutionID, '3-clean', 'WWI_Staging.clean.InvoiceLines', COUNT_BIG(*), SUM(ExtendedPrice - TaxAmount), NULL
    FROM WWI_Staging.clean.InvoiceLines
    UNION ALL
    SELECT @ExecutionID, '3b-cuarentena', 'WWI_Staging.quarantine (InvoiceLines pendientes)', COUNT_BIG(DISTINCT q.BusinessKey), NULL, 'Rechazadas por reglas de calidad'
    FROM WWI_Staging.quarantine.RejectedRecord q
    WHERE q.SourceObject = 'Sales.InvoiceLines' AND q.Status = 'pendiente'
      AND NOT EXISTS (SELECT 1 FROM WWI_Staging.clean.InvoiceLines c WHERE CAST(c.InvoiceLineID AS nvarchar(100)) = q.BusinessKey)
    UNION ALL
    SELECT @ExecutionID, '4-dw', 'WWI_DW.dw.FactSales', COUNT_BIG(*), SUM(NetAmount), NULL
    FROM dw.FactSales;

    SELECT Layer, ObjectName, RowCountValue, AmountValue, Notes FROM ops.Reconciliation WHERE ExecutionID = @ExecutionID ORDER BY Layer;
END
GO
