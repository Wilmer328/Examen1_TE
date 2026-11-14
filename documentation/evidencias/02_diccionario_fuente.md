# Diccionario de datos — fuente (tablas usadas)

Generado automáticamente el 2026-11-14 13:49 por `documentation/generar_evidencias.py`.

Columnas marcadas como *extraída* se copian a staging; el resto (teléfonos, correos, fotos, geografía) se excluye por minimización de datos.

## Application.Cities

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| CityID | int | no | PK | sí |
| CityName | nvarchar(50) | no |  | sí |
| StateProvinceID | int | no |  FK?Application.StateProvinces | sí |
| Location | geography | sí |  |  |
| LatestRecordedPopulation | bigint | sí |  | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Application.Countries

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| CountryID | int | no | PK | sí |
| CountryName | nvarchar(60) | no |  | sí |
| FormalName | nvarchar(60) | no |  |  |
| IsoAlpha3Code | nvarchar(3) | sí |  |  |
| IsoNumericCode | int | sí |  |  |
| CountryType | nvarchar(20) | sí |  |  |
| LatestRecordedPopulation | bigint | sí |  |  |
| Continent | nvarchar(30) | no |  | sí |
| Region | nvarchar(30) | no |  | sí |
| Subregion | nvarchar(30) | no |  | sí |
| Border | geography | sí |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Application.People

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| PersonID | int | no | PK | sí |
| FullName | nvarchar(50) | no |  | sí |
| PreferredName | nvarchar(50) | no |  | sí |
| SearchName | nvarchar(101) | no |  |  |
| IsPermittedToLogon | bit | no |  |  |
| LogonName | nvarchar(50) | sí |  |  |
| IsExternalLogonProvider | bit | no |  |  |
| HashedPassword | varbinary | sí |  |  |
| IsSystemUser | bit | no |  |  |
| IsEmployee | bit | no |  | sí |
| IsSalesperson | bit | no |  | sí |
| UserPreferences | nvarchar(max) | sí |  |  |
| PhoneNumber | nvarchar(20) | sí |  |  |
| FaxNumber | nvarchar(20) | sí |  |  |
| EmailAddress | nvarchar(256) | sí |  |  |
| Photo | varbinary | sí |  |  |
| CustomFields | nvarchar(max) | sí |  |  |
| OtherLanguages | nvarchar(max) | sí |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Application.StateProvinces

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| StateProvinceID | int | no | PK | sí |
| StateProvinceCode | nvarchar(5) | no |  | sí |
| StateProvinceName | nvarchar(50) | no |  | sí |
| CountryID | int | no |  FK?Application.Countries | sí |
| SalesTerritory | nvarchar(50) | no |  | sí |
| Border | geography | sí |  |  |
| LatestRecordedPopulation | bigint | sí |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Sales.BuyingGroups

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| BuyingGroupID | int | no | PK | sí |
| BuyingGroupName | nvarchar(50) | no |  | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Sales.CustomerCategories

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| CustomerCategoryID | int | no | PK | sí |
| CustomerCategoryName | nvarchar(50) | no |  | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Sales.Customers

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| CustomerID | int | no | PK | sí |
| CustomerName | nvarchar(100) | no |  | sí |
| BillToCustomerID | int | no |  FK?Sales.Customers | sí |
| CustomerCategoryID | int | no |  FK?Sales.CustomerCategories | sí |
| BuyingGroupID | int | sí |  FK?Sales.BuyingGroups | sí |
| PrimaryContactPersonID | int | no |  FK?Application.People |  |
| AlternateContactPersonID | int | sí |  FK?Application.People |  |
| DeliveryMethodID | int | no |  FK?Application.DeliveryMethods |  |
| DeliveryCityID | int | no |  FK?Application.Cities | sí |
| PostalCityID | int | no |  FK?Application.Cities |  |
| CreditLimit | decimal(18,2) | sí |  | sí |
| AccountOpenedDate | date | no |  | sí |
| StandardDiscountPercentage | decimal(18,3) | no |  | sí |
| IsStatementSent | bit | no |  |  |
| IsOnCreditHold | bit | no |  | sí |
| PaymentDays | int | no |  | sí |
| PhoneNumber | nvarchar(20) | no |  |  |
| FaxNumber | nvarchar(20) | no |  |  |
| DeliveryRun | nvarchar(5) | sí |  |  |
| RunPosition | nvarchar(5) | sí |  |  |
| WebsiteURL | nvarchar(256) | no |  |  |
| DeliveryAddressLine1 | nvarchar(60) | no |  |  |
| DeliveryAddressLine2 | nvarchar(60) | sí |  |  |
| DeliveryPostalCode | nvarchar(10) | no |  |  |
| DeliveryLocation | geography | sí |  |  |
| PostalAddressLine1 | nvarchar(60) | no |  |  |
| PostalAddressLine2 | nvarchar(60) | sí |  |  |
| PostalPostalCode | nvarchar(10) | no |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Sales.InvoiceLines

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| InvoiceLineID | int | no | PK | sí |
| InvoiceID | int | no |  FK?Sales.Invoices | sí |
| StockItemID | int | no |  FK?Warehouse.StockItems | sí |
| Description | nvarchar(100) | no |  | sí |
| PackageTypeID | int | no |  FK?Warehouse.PackageTypes |  |
| Quantity | int | no |  | sí |
| UnitPrice | decimal(18,2) | sí |  | sí |
| TaxRate | decimal(18,3) | no |  | sí |
| TaxAmount | decimal(18,2) | no |  | sí |
| LineProfit | decimal(18,2) | no |  | sí |
| ExtendedPrice | decimal(18,2) | no |  | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| LastEditedWhen | datetime2 | no |  | sí |

## Sales.Invoices

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| InvoiceID | int | no | PK | sí |
| CustomerID | int | no |  FK?Sales.Customers | sí |
| BillToCustomerID | int | no |  FK?Sales.Customers | sí |
| OrderID | int | sí |  FK?Sales.Orders | sí |
| DeliveryMethodID | int | no |  FK?Application.DeliveryMethods |  |
| ContactPersonID | int | no |  FK?Application.People |  |
| AccountsPersonID | int | no |  FK?Application.People |  |
| SalespersonPersonID | int | no |  FK?Application.People | sí |
| PackedByPersonID | int | no |  FK?Application.People |  |
| InvoiceDate | date | no |  | sí |
| CustomerPurchaseOrderNumber | nvarchar(20) | sí |  |  |
| IsCreditNote | bit | no |  | sí |
| CreditNoteReason | nvarchar(max) | sí |  |  |
| Comments | nvarchar(max) | sí |  |  |
| DeliveryInstructions | nvarchar(max) | sí |  |  |
| InternalComments | nvarchar(max) | sí |  |  |
| TotalDryItems | int | no |  |  |
| TotalChillerItems | int | no |  |  |
| DeliveryRun | nvarchar(5) | sí |  |  |
| RunPosition | nvarchar(5) | sí |  |  |
| ReturnedDeliveryData | nvarchar(max) | sí |  |  |
| ConfirmedDeliveryTime | datetime2 | sí |  |  |
| ConfirmedReceivedBy | nvarchar(4000) | sí |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| LastEditedWhen | datetime2 | no |  | sí |

## Warehouse.StockGroups

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| StockGroupID | int | no | PK | sí |
| StockGroupName | nvarchar(50) | no |  | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Warehouse.StockItems

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| StockItemID | int | no | PK | sí |
| StockItemName | nvarchar(100) | no |  | sí |
| SupplierID | int | no |  FK?Purchasing.Suppliers |  |
| ColorID | int | sí |  FK?Warehouse.Colors |  |
| UnitPackageID | int | no |  FK?Warehouse.PackageTypes |  |
| OuterPackageID | int | no |  FK?Warehouse.PackageTypes |  |
| Brand | nvarchar(50) | sí |  | sí |
| Size | nvarchar(20) | sí |  | sí |
| LeadTimeDays | int | no |  |  |
| QuantityPerOuter | int | no |  |  |
| IsChillerStock | bit | no |  | sí |
| Barcode | nvarchar(50) | sí |  |  |
| TaxRate | decimal(18,3) | no |  | sí |
| UnitPrice | decimal(18,2) | no |  | sí |
| RecommendedRetailPrice | decimal(18,2) | sí |  | sí |
| TypicalWeightPerUnit | decimal(18,3) | no |  |  |
| MarketingComments | nvarchar(max) | sí |  |  |
| InternalComments | nvarchar(max) | sí |  |  |
| Photo | varbinary | sí |  |  |
| CustomFields | nvarchar(max) | sí |  |  |
| Tags | nvarchar(max) | sí |  |  |
| SearchDetails | nvarchar(max) | no |  |  |
| LastEditedBy | int | no |  FK?Application.People |  |
| ValidFrom | datetime2 | no |  | sí |
| ValidTo | datetime2 | no |  |  |

## Warehouse.StockItemStockGroups

| columna | tipo | nulo | clave | extraída |
|---|---|---|---|---|
| StockItemStockGroupID | int | no | PK | sí |
| StockItemID | int | no |  FK?Warehouse.StockItems | sí |
| StockGroupID | int | no |  FK?Warehouse.StockGroups | sí |
| LastEditedBy | int | no |  FK?Application.People |  |
| LastEditedWhen | datetime2 | no |  | sí |

