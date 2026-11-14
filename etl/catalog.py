"""Catálogo declarativo de objetos extraídos y reglas de calidad/transformación.

Cada entidad define:
  - source: tabla origen en WideWorldImporters
  - columns: columnas extraídas (minimización: no se extraen teléfonos, correos ni fotos)
  - watermark: columna para la carga incremental (ValidFrom en tablas temporales, LastEditedWhen en el resto)
  - key: clave de negocio (duplicados -> regla de supervivencia: último watermark, luego último _raw_id)
  - transforms: expresión SQL de estandarización por columna (alias de lote: s)
  - reject_rules: (id, dimensión de calidad, descripción, predicado SQL que identifica el registro INVÁLIDO)
El orden de la lista es el orden de procesamiento (catálogos antes que transacciones).
"""
from __future__ import annotations

from dataclasses import dataclass, field


def trim(col: str) -> str:
    """Quita espacios extremos y colapsa espacios dobles; cadena vacía -> NULL."""
    return f"NULLIF(REPLACE(REPLACE(LTRIM(RTRIM(s.{col})), '  ', ' '), '  ', ' '), '')"


@dataclass
class Rule:
    rule_id: str
    dimension: str
    description: str
    predicate: str


@dataclass
class Entity:
    name: str
    source: str
    columns: list[str]
    watermark: str
    key: str
    transforms: dict[str, str] = field(default_factory=dict)
    reject_rules: list[Rule] = field(default_factory=list)

    @property
    def raw_table(self) -> str:
        return f"raw.{self.name}"

    @property
    def clean_table(self) -> str:
        return f"clean.{self.name}"


ENTITIES: list[Entity] = [
    Entity("Countries", "Application.Countries",
           ["CountryID", "CountryName", "Continent", "Region", "Subregion", "ValidFrom"], "ValidFrom", "CountryID",
           {"CountryName": trim("CountryName"), "Continent": trim("Continent"), "Region": trim("Region"),
            "Subregion": trim("Subregion")},
           [Rule("R-CO-01", "Completitud", "Nombre de país obligatorio", f"{trim('CountryName')} IS NULL")]),
    Entity("StateProvinces", "Application.StateProvinces",
           ["StateProvinceID", "StateProvinceCode", "StateProvinceName", "CountryID", "SalesTerritory", "ValidFrom"],
           "ValidFrom", "StateProvinceID",
           {"StateProvinceCode": f"UPPER({trim('StateProvinceCode')})", "StateProvinceName": trim("StateProvinceName"),
            "SalesTerritory": f"ISNULL({trim('SalesTerritory')}, 'Desconocido')"},
           [Rule("R-SP-01", "Completitud", "Nombre de estado obligatorio", f"{trim('StateProvinceName')} IS NULL")]),
    Entity("Cities", "Application.Cities",
           ["CityID", "CityName", "StateProvinceID", "LatestRecordedPopulation", "ValidFrom"], "ValidFrom", "CityID",
           {"CityName": trim("CityName"),
            # Población negativa no es válida -> se marca como desconocida (NULL), no como cero
            "LatestRecordedPopulation": "CASE WHEN s.LatestRecordedPopulation < 0 THEN NULL ELSE s.LatestRecordedPopulation END"},
           [Rule("R-CI-01", "Completitud", "Nombre de ciudad obligatorio", f"{trim('CityName')} IS NULL"),
            Rule("R-CI-02", "Integridad", "Ciudad sin estado/provincia", "s.StateProvinceID IS NULL")]),
    Entity("People", "Application.People",
           ["PersonID", "FullName", "PreferredName", "IsEmployee", "IsSalesperson", "ValidFrom"], "ValidFrom", "PersonID",
           {"FullName": trim("FullName"), "PreferredName": trim("PreferredName")},
           [Rule("R-PE-01", "Completitud", "Nombre completo obligatorio", f"{trim('FullName')} IS NULL")]),
    Entity("CustomerCategories", "Sales.CustomerCategories",
           ["CustomerCategoryID", "CustomerCategoryName", "ValidFrom"], "ValidFrom", "CustomerCategoryID",
           {"CustomerCategoryName": trim("CustomerCategoryName")},
           [Rule("R-CC-01", "Completitud", "Nombre de categoría obligatorio", f"{trim('CustomerCategoryName')} IS NULL")]),
    Entity("BuyingGroups", "Sales.BuyingGroups",
           ["BuyingGroupID", "BuyingGroupName", "ValidFrom"], "ValidFrom", "BuyingGroupID",
           {"BuyingGroupName": trim("BuyingGroupName")},
           [Rule("R-BG-01", "Completitud", "Nombre de grupo obligatorio", f"{trim('BuyingGroupName')} IS NULL")]),
    Entity("Customers", "Sales.Customers",
           ["CustomerID", "CustomerName", "BillToCustomerID", "CustomerCategoryID", "BuyingGroupID", "DeliveryCityID",
            "CreditLimit", "AccountOpenedDate", "StandardDiscountPercentage", "IsOnCreditHold", "PaymentDays", "ValidFrom"],
           "ValidFrom", "CustomerID",
           # CreditLimit NULL = "No aplica" (cliente sin límite): se conserva NULL, NO se reemplaza por 0.
           # BuyingGroupID NULL = "No aplica" (cliente independiente): se resuelve en ready como 'Sin grupo de compra'.
           {"CustomerName": trim("CustomerName")},
           [Rule("R-CU-01", "Completitud", "Nombre de cliente obligatorio", f"{trim('CustomerName')} IS NULL"),
            Rule("R-CU-02", "Validez", "Días de pago no pueden ser negativos", "s.PaymentDays < 0"),
            Rule("R-CU-03", "Validez", "Límite de crédito no puede ser negativo", "s.CreditLimit < 0")]),
    Entity("StockGroups", "Warehouse.StockGroups",
           ["StockGroupID", "StockGroupName", "ValidFrom"], "ValidFrom", "StockGroupID",
           {"StockGroupName": trim("StockGroupName")},
           [Rule("R-SG-01", "Completitud", "Nombre de grupo de stock obligatorio", f"{trim('StockGroupName')} IS NULL")]),
    Entity("StockItemStockGroups", "Warehouse.StockItemStockGroups",
           ["StockItemStockGroupID", "StockItemID", "StockGroupID", "LastEditedWhen"], "LastEditedWhen",
           "StockItemStockGroupID", {},
           [Rule("R-SISG-01", "Integridad", "Relación artículo-grupo incompleta", "s.StockItemID IS NULL OR s.StockGroupID IS NULL")]),
    Entity("StockItems", "Warehouse.StockItems",
           ["StockItemID", "StockItemName", "Brand", "Size", "IsChillerStock", "TaxRate", "UnitPrice",
            "RecommendedRetailPrice", "ValidFrom"], "ValidFrom", "StockItemID",
           # Brand NULL = Desconocido ('Sin marca'); Size NULL = No aplica ('N/A')
           {"StockItemName": trim("StockItemName"), "Brand": f"ISNULL({trim('Brand')}, 'Sin marca')",
            "Size": f"ISNULL({trim('Size')}, 'N/A')"},
           [Rule("R-SI-01", "Completitud", "Nombre de artículo obligatorio", f"{trim('StockItemName')} IS NULL"),
            Rule("R-SI-02", "Validez", "Precio de lista debe ser > 0", "s.UnitPrice IS NULL OR s.UnitPrice <= 0")]),
    Entity("Invoices", "Sales.Invoices",
           ["InvoiceID", "CustomerID", "BillToCustomerID", "OrderID", "SalespersonPersonID", "InvoiceDate",
            "IsCreditNote", "LastEditedWhen"], "LastEditedWhen", "InvoiceID", {},
           [Rule("R-IN-01", "Validez", "Fecha de factura nula, anterior a 2013 o futura",
                 "s.InvoiceDate IS NULL OR s.InvoiceDate < '2013-01-01' OR s.InvoiceDate > CAST(SYSDATETIME() AS date)"),
            Rule("R-IN-02", "Completitud", "Factura sin cliente", "s.CustomerID IS NULL")]),
    Entity("InvoiceLines", "Sales.InvoiceLines",
           ["InvoiceLineID", "InvoiceID", "StockItemID", "Description", "Quantity", "UnitPrice", "TaxRate",
            "TaxAmount", "LineProfit", "ExtendedPrice", "LastEditedWhen"], "LastEditedWhen", "InvoiceLineID",
           {"Description": trim("Description"),
            # Imputación confiable: si falta UnitPrice se DERIVA de ExtendedPrice, TaxAmount y Quantity (marcado)
            "UnitPrice": "COALESCE(s.UnitPrice, ROUND((s.ExtendedPrice - s.TaxAmount) / NULLIF(s.Quantity, 0), 2))",
            "IsUnitPriceDerived": "CASE WHEN s.UnitPrice IS NULL THEN 1 ELSE 0 END",
            "IsQuantityOutlier": "CASE WHEN s.Quantity > @qty_outlier THEN 1 ELSE 0 END"},
           [Rule("R-IL-01", "Validez", "Cantidad debe ser > 0 (no existen notas de crédito en el alcance)",
                 "s.Quantity IS NULL OR s.Quantity <= 0"),
            Rule("R-IL-02", "Validez", "Precio unitario negativo", "s.UnitPrice < 0"),
            Rule("R-IL-03", "Validez", "Tasa de impuesto fuera de 0-100", "s.TaxRate IS NULL OR s.TaxRate NOT BETWEEN 0 AND 100"),
            Rule("R-IL-04", "Consistencia", "ExtendedPrice <> Quantity*UnitPrice + TaxAmount (tolerancia 0.05)",
                 "s.UnitPrice IS NOT NULL AND ABS(s.ExtendedPrice - (s.Quantity * s.UnitPrice + s.TaxAmount)) > 0.05"),
            Rule("R-IL-05", "Integridad", "Línea huérfana: su factura no existe en clean (se reintenta en la próxima carga)",
                 "NOT EXISTS (SELECT 1 FROM clean.Invoices i WHERE i.InvoiceID = s.InvoiceID)"),
            Rule("R-IL-06", "Completitud", "Línea sin artículo", "s.StockItemID IS NULL")]),
]

ENTITY_BY_NAME = {e.name: e for e in ENTITIES}
