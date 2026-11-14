# Perfil de datos de la fuente (WideWorldImporters)

Generado automáticamente el 2026-11-14 13:49 por `documentation/generar_evidencias.py`.

## Application.Countries — 190 filas

Clave: `CountryID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| CountryID | 0.0 | 190 | 1 | 241 | 1 (1); 3 (1); 4 (1) |
| CountryName | 0.0 | 190 | Afghanistan | Zimbabwe | Afghanistan (1); Albania (1); Algeria (1) |
| Continent | 0.0 | 7 | Africa | South America | Africa (50); Asia (46); Europe (43) |
| Region | 0.0 | 5 | Africa | Oceania | Africa (52); Asia (47); Europe (43) |
| Subregion | 0.0 | 22 | Australia and New Zealand | Western Europe | Eastern Africa (17); Western Asia (17); Western Africa (15) |
| ValidFrom | 0.0 | 5 | 2013-01-01 00:00:00.0000000 | 2022-10-07 22:01:58.6226027 | 2013-01-01 00:00:00.0000000 (154); 2015-07-01 16:00:00.0000000 (18); 2013-07-01  |

## Application.StateProvinces — 53 filas

Clave: `StateProvinceID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| StateProvinceID | 0.0 | 53 | 1 | 53 | 40 (1); 48 (1); 2 (1) |
| StateProvinceCode | 0.0 | 53 | AK | WY | AZ (1); AR (1); AL (1) |
| StateProvinceName | 0.0 | 53 | Alabama | Wyoming | Alabama (1); Alaska (1); Arizona (1) |
| CountryID | 0.0 | 1 | 230 | 230 | 230 (53) |
| SalesTerritory | 0.0 | 9 | External | Southwest | Southeast (12); Plains (7); Far West (6) |
| ValidFrom | 0.0 | 9 | 2013-01-01 00:00:00.0000000 | 2015-07-01 16:00:00.0000000 | 2014-07-01 16:00:00.0000000 (15); 2015-07-01 16:00:00.0000000 (10); 2013-07-01 1 |

## Application.Cities — 37,940 filas

Clave: `CityID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| CityID | 0.0 | 37940 | 1 | 38186 | 3 (1); 6 (1); 28 (1) |
| CityName | 0.0 | 23272 | Aaronsburg | Zwolle | Franklin (32); Clinton (29); Washington (28) |
| StateProvinceID | 0.0 | 53 | 1 | 53 | 45 (2395); 39 (1830); 33 (1650) |
| LatestRecordedPopulation | 29.12 | 9324 | 0 | 8175133 | None (11048); 112 (37); 68 (37) |
| ValidFrom | 0.0 | 4 | 2013-01-01 00:00:00.0000000 | 2015-07-01 16:00:00.0000000 | 2013-01-01 00:00:00.0000000 (37912); 2015-07-01 16:00:00.0000000 (13); 2013-07-0 |

## Application.People — 1,111 filas

Clave: `PersonID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| PersonID | 0.0 | 1111 | 1 | 3261 | 1 (1); 4 (1); 5 (1) |
| FullName | 0.0 | 1111 | Aahlada Thota | Zuzana Kuchtova | Aakriti Byrraju (1); Aakriti Bhamidipati (1); Aakarsha Nookala (1) |
| PreferredName | 0.0 | 880 | Aahlada | Zuzana | David (5); Dhanishta (5); Daniela (4) |
| IsEmployee | 0.0 | 2 | 0 | 1 | 0 (1092); 1 (19) |
| IsSalesperson | 0.0 | 2 | 0 | 1 | 0 (1101); 1 (10) |
| ValidFrom | 0.0 | 58 | 2013-01-01 00:00:00.0000000 | 2016-05-31 23:14:00.0000000 | 2013-01-01 00:00:00.0000000 (873); 2016-05-31 23:14:00.0000000 (182); 2015-01-16 |

## Sales.CustomerCategories — 8 filas

Clave: `CustomerCategoryID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| CustomerCategoryID | 0.0 | 8 | 1 | 8 | 1 (1); 5 (1); 7 (1) |
| CustomerCategoryName | 0.0 | 8 | Agent | Wholesaler | Agent (1); Computer Store (1); Corporate (1) |
| ValidFrom | 0.0 | 2 | 2013-01-01 00:00:00.0000000 | 2014-01-01 16:15:00.0000000 | 2013-01-01 00:00:00.0000000 (7); 2014-01-01 16:15:00.0000000 (1) |

## Sales.BuyingGroups — 2 filas

Clave: `BuyingGroupID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| BuyingGroupID | 0.0 | 2 | 1 | 2 | 1 (1); 2 (1) |
| BuyingGroupName | 0.0 | 2 | Tailspin Toys | Wingtip Toys | Tailspin Toys (1); Wingtip Toys (1) |
| ValidFrom | 0.0 | 1 | 2013-01-01 00:00:00.0000000 | 2013-01-01 00:00:00.0000000 | 2013-01-01 00:00:00.0000000 (2) |

## Sales.Customers — 663 filas

Clave: `CustomerID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| CustomerID | 0.0 | 663 | 1 | 1061 | 841 (1); 83 (1); 595 (1) |
| CustomerName | 0.0 | 663 | Aakriti Byrraju | Yves Belisle | Tailspin Toys (Head Office) (1); Tailspin Toys (Sylvanite, MT) (1); Tailspin Toy |
| BillToCustomerID | 0.0 | 263 | 1 | 1061 | 401 (201); 1 (201); 802 (1) |
| CustomerCategoryID | 0.0 | 5 | 3 | 7 | 3 (458); 4 (59); 5 (51) |
| BuyingGroupID | 39.37 | 2 | 1 | 2 | None (261); 2 (201); 1 (201) |
| DeliveryCityID | 0.0 | 655 | 15 | 38184 | 242 (2); 6221 (2); 9791 (2) |
| CreditLimit | 60.63 | 56 | 1100.00 | 4630.50 | None (402); 3300.00 (17); 3500.00 (13) |
| AccountOpenedDate | 0.0 | 62 | 2013-01-01 | 2016-05-07 | 2013-01-01 (602); 2013-03-25 (1); 2013-02-22 (1) |
| StandardDiscountPercentage | 0.0 | 1 | 0.000 | 0.000 | 0.000 (663) |
| IsOnCreditHold | 0.0 | 1 | 0 | 0 | 0 (663) |
| PaymentDays | 0.0 | 1 | 7 | 7 | 7 (663) |
| ValidFrom | 0.0 | 59 | 2013-01-01 00:00:00.0000000 | 2026-11-14 19:16:43.1850738 | 2013-01-01 00:00:00.0000000 (562); 2013-07-01 16:00:00.0000000 (16); 2015-07-01  |

## Warehouse.StockGroups — 10 filas

Clave: `StockGroupID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| StockGroupID | 0.0 | 10 | 1 | 10 | 5 (1); 2 (1); 6 (1) |
| StockGroupName | 0.0 | 10 | Airline Novelties | USB Novelties | Airline Novelties (1); Clothing (1); Computing Novelties (1) |
| ValidFrom | 0.0 | 2 | 2013-01-01 00:00:00.0000000 | 2016-01-01 16:00:00.0000000 | 2013-01-01 00:00:00.0000000 (9); 2016-01-01 16:00:00.0000000 (1) |

## Warehouse.StockItemStockGroups — 442 filas

Clave: `StockItemStockGroupID` · watermark: `LastEditedWhen`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| StockItemStockGroupID | 0.0 | 442 | 1 | 442 | 2 (1); 5 (1); 8 (1) |
| StockItemID | 0.0 | 227 | 1 | 227 | 2 (3); 1 (3); 4 (3) |
| StockGroupID | 0.0 | 9 | 1 | 10 | 1 (91); 6 (83); 2 (74) |
| LastEditedWhen | 0.0 | 5 | 2013-01-01 00:00:00.0000000 | 2016-01-05 00:00:00.0000000 | 2013-01-01 00:00:00.0000000 (434); 2016-01-04 00:00:00.0000000 (2); 2016-01-02 0 |

## Warehouse.StockItems — 227 filas

Clave: `StockItemID` · watermark: `ValidFrom`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| StockItemID | 0.0 | 227 | 1 | 227 | 3 (1); 76 (1); 77 (1) |
| StockItemName | 0.0 | 227 | "The Gu" red shirt XML tag t-shirt (Black) 3XL | White chocolate snow balls 250g | "The Gu" red shirt XML tag t-shirt (Blac (1); "The Gu" red shirt XML tag t-shirt |
| Brand | 92.07 | 1 | Northwind | Northwind | None (209); Northwind (18) |
| Size | 28.19 | 43 | 1.5m | XXS | None (64); XL (12); L (11) |
| IsChillerStock | 0.0 | 2 | 0 | 1 | 0 (219); 1 (8) |
| TaxRate | 0.0 | 2 | 10.000 | 15.000 | 15.000 (219); 10.000 (8) |
| UnitPrice | 0.0 | 57 | 0.66 | 1899.00 | 13.00 (42); 18.00 (35); 32.00 (34) |
| RecommendedRetailPrice | 0.0 | 57 | 0.99 | 2839.01 | 19.44 (42); 26.91 (35); 47.84 (34) |
| ValidFrom | 0.0 | 10 | 2016-05-31 23:00:00.0000000 | 2016-05-31 23:12:00.0000000 | 2016-05-31 23:12:00.0000000 (67); 2016-05-31 23:00:00.0000000 (55); 2016-05-31 2 |

## Sales.Invoices — 71,006 filas

Clave: `InvoiceID` · watermark: `LastEditedWhen`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| InvoiceID | 0.0 | 71006 | 1 | 71092 | 1 (1); 2 (1); 3 (1) |
| CustomerID | 0.0 | 663 | 1 | 1061 | 831 (146); 110 (141); 90 (140) |
| BillToCustomerID | 0.0 | 263 | 1 | 1061 | 1 (22462); 401 (22319); 831 (146) |
| OrderID | 0.7 | 70510 | 1 | 73586 | None (496); 3 (1); 2 (1) |
| SalespersonPersonID | 0.0 | 10 | 2 | 20 | 16 (7239); 2 (7206); 6 (7125) |
| InvoiceDate | 0.0 | 1075 | 2013-01-01 | 2016-06-07 | 2016-01-06 (117); 2016-04-18 (117); 2016-02-24 (116) |
| IsCreditNote | 0.0 | 1 | 0 | 0 | 0 (71006) |
| LastEditedWhen | 0.0 | 1075 | 2013-01-02 07:00:00.0000000 | 2026-11-14 13:16:42.9677070 | 2016-04-19 07:00:00.0000000 (117); 2016-01-07 07:00:00.0000000 (117); 2016-02-25 |

## Sales.InvoiceLines — 229,884 filas

Clave: `InvoiceLineID` · watermark: `LastEditedWhen`

| columna | % nulos | distintos | mín | máx | valores frecuentes |
|---|---|---|---|---|---|
| InvoiceLineID | 0.0 | 229884 | 1 | 229884 | 1 (1); 2 (1); 3 (1) |
| InvoiceID | 0.0 | 71006 | 1 | 71092 | 34 (5); 95 (5); 96 (5) |
| StockItemID | 0.0 | 227 | 1 | 227 | 104 (1134); 120 (1129); 167 (1128) |
| Description | 0.0 | 230 |   SIMULADO   precio  nulo   | White chocolate snow balls 250g | Alien officer hoodie (Black) 3XL (1134); Dinosaur battery-powered slippers (Gree |
| Quantity | 0.0 | 62 | 0 | 360 | 10 (15913); 5 (12972); 1 (12812) |
| UnitPrice | 0.0 | 63 | 0.66 | 1899.00 | 13.00 (44889); 32.00 (35454); 18.00 (34551) |
| TaxRate | 0.0 | 2 | 10.000 | 15.000 | 15.000 (228848); 10.000 (1036) |
| TaxAmount | 0.0 | 495 | 0.00 | 2848.50 | 13.65 (4645); 1.95 (4615); 5.85 (4535) |
| LineProfit | 0.0 | 572 | -645.00 | 9200.00 | 85.00 (5100); 68.00 (4700); 59.50 (4645) |
| ExtendedPrice | 0.0 | 500 | 0.00 | 21838.50 | 104.65 (4645); 14.95 (4615); 44.85 (4535) |
| LastEditedWhen | 0.0 | 1076 | 2013-01-01 12:00:00.0000000 | 2026-11-14 13:16:43.1235858 | 2016-05-04 12:00:00.0000000 (395); 2015-01-21 12:00:00.0000000 (390); 2015-11-24 |

## Hallazgos del perfilado

- Posibles duplicados de negocio en líneas (misma factura, artículo, cantidad y precio): **0**. La clave técnica `InvoiceLineID` es única; estas filas se conservan (pueden ser líneas legítimas repetidas).
- Líneas con `ExtendedPrice` inconsistente (> 0.05): **1** (la fuente original no tiene ninguna; las que aparezcan provienen de la simulación de registros sucios y van a cuarentena por R-IL-04).
- Cantidad: media 39.2, desviación 54.5, máximo 360 → umbral de outlier media+4σ = 257.
- Artículos que pertenecen a más de un grupo de stock (relación N:M): **133** → riesgo de multiplicar medidas; se asigna una categoría principal (menor StockGroupID).
- `Customers.BuyingGroupID` y `Customers.CreditLimit` tienen nulos con significado de negocio (“No aplica”): se conservan.
- `StockItems.Brand` y `Size` tienen nulos: se estandarizan como 'Sin marca' / 'N/A'.
