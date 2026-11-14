"""SIMULACIÓN de operaciones nuevas en la fuente (para demostrar carga incremental, SCD2,
calidad/cuarentena y alertas). Todo lo insertado se identifica como simulado:
  - Facturas: CustomerPurchaseOrderNumber = 'SIM-<fecha>' y Comments = 'SIMULADO'.

Estrategia: copia las facturas del MISMO día de la semana 52 semanas antes (estacionalidad real),
con fecha nueva a continuación del último día existente. --factor < 1 en un territorio simula una caída.

Ejemplos:
    python -m etl.simulate_source_changes --days 7
    python -m etl.simulate_source_changes --days 7 --territory Southeast --factor 0.4
    python -m etl.simulate_source_changes --dirty           # agrega registros con problemas de calidad
    python -m etl.simulate_source_changes --scd2 --customer-id 1   # cambia la categoría de un cliente
Requiere permisos de escritura en la fuente (cuenta administradora local, NO la cuenta etl_user).
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from common import config, db

COPY_DAY_SQL = """
SET NOCOUNT ON; SET XACT_ABORT ON;
DECLARE @new date = ?, @src date = DATEADD(DAY, -364, ?), @territory nvarchar(50) = ?, @factor float = ?, @tag nvarchar(20) = ?;
CREATE TABLE #map (OldInvoiceID int PRIMARY KEY, NewInvoiceID int);
INSERT #map (OldInvoiceID, NewInvoiceID)
SELECT i.InvoiceID, NEXT VALUE FOR Sequences.InvoiceID
FROM Sales.Invoices i
JOIN Sales.Customers c ON c.CustomerID = i.CustomerID
JOIN Application.Cities ci ON ci.CityID = c.DeliveryCityID
JOIN Application.StateProvinces sp ON sp.StateProvinceID = ci.StateProvinceID
WHERE i.InvoiceDate = @src
  AND ABS(CHECKSUM(NEWID())) % 1000 < 1000 * IIF(@territory IS NULL OR sp.SalesTerritory = @territory, @factor, 1.0);

BEGIN TRAN;
INSERT Sales.Invoices (InvoiceID, CustomerID, BillToCustomerID, OrderID, DeliveryMethodID, ContactPersonID, AccountsPersonID,
    SalespersonPersonID, PackedByPersonID, InvoiceDate, CustomerPurchaseOrderNumber, IsCreditNote, CreditNoteReason, Comments,
    DeliveryInstructions, InternalComments, TotalDryItems, TotalChillerItems, DeliveryRun, RunPosition, ReturnedDeliveryData,
    LastEditedBy, LastEditedWhen)
SELECT m.NewInvoiceID, i.CustomerID, i.BillToCustomerID, NULL, i.DeliveryMethodID, i.ContactPersonID, i.AccountsPersonID,
    i.SalespersonPersonID, i.PackedByPersonID, @new, @tag, 0, NULL, N'SIMULADO', i.DeliveryInstructions, NULL,
    i.TotalDryItems, i.TotalChillerItems, i.DeliveryRun, i.RunPosition, NULL, 1, SYSDATETIME()
FROM #map m JOIN Sales.Invoices i ON i.InvoiceID = m.OldInvoiceID;

INSERT Sales.InvoiceLines (InvoiceLineID, InvoiceID, StockItemID, Description, PackageTypeID, Quantity, UnitPrice, TaxRate,
    TaxAmount, LineProfit, ExtendedPrice, LastEditedBy, LastEditedWhen)
SELECT NEXT VALUE FOR Sequences.InvoiceLineID, m.NewInvoiceID, l.StockItemID, l.Description, l.PackageTypeID, l.Quantity,
    l.UnitPrice, l.TaxRate, l.TaxAmount, l.LineProfit, l.ExtendedPrice, 1, SYSDATETIME()
FROM #map m JOIN Sales.InvoiceLines l ON l.InvoiceID = m.OldInvoiceID;
COMMIT;
SELECT (SELECT COUNT(*) FROM #map) AS invoices,
       (SELECT COUNT(*) FROM Sales.InvoiceLines l JOIN #map m ON m.NewInvoiceID = l.InvoiceID) AS lines;
"""

DIRTY_SQL = """
SET NOCOUNT ON; SET XACT_ABORT ON;
DECLARE @inv int = (SELECT MAX(InvoiceID) FROM Sales.Invoices WHERE Comments = N'SIMULADO');
IF @inv IS NULL THROW 50001, 'Primero simule al menos un día (--days).', 1;
BEGIN TRAN;
-- (1) Cantidad = 0 -> viola R-IL-01 -> cuarentena
INSERT Sales.InvoiceLines (InvoiceLineID, InvoiceID, StockItemID, Description, PackageTypeID, Quantity, UnitPrice, TaxRate,
    TaxAmount, LineProfit, ExtendedPrice, LastEditedBy, LastEditedWhen)
VALUES (NEXT VALUE FOR Sequences.InvoiceLineID, @inv, 1, N'SIMULADO cantidad cero', 7, 0, 10.00, 15.000, 0, 0, 0, 1, SYSDATETIME());
-- (2) UnitPrice NULL -> se DERIVA de (ExtendedPrice - TaxAmount) / Quantity y se marca IsUnitPriceDerived = 1
INSERT Sales.InvoiceLines (InvoiceLineID, InvoiceID, StockItemID, Description, PackageTypeID, Quantity, UnitPrice, TaxRate,
    TaxAmount, LineProfit, ExtendedPrice, LastEditedBy, LastEditedWhen)
VALUES (NEXT VALUE FOR Sequences.InvoiceLineID, @inv, 2, N'  SIMULADO   precio  nulo  ', 7, 4, NULL, 15.000, 6.00, 12.00, 46.00, 1, SYSDATETIME());
-- (3) Inconsistencia ExtendedPrice <> Quantity*UnitPrice + Tax -> viola R-IL-04 -> cuarentena
INSERT Sales.InvoiceLines (InvoiceLineID, InvoiceID, StockItemID, Description, PackageTypeID, Quantity, UnitPrice, TaxRate,
    TaxAmount, LineProfit, ExtendedPrice, LastEditedBy, LastEditedWhen)
VALUES (NEXT VALUE FOR Sequences.InvoiceLineID, @inv, 3, N'SIMULADO inconsistente', 7, 2, 10.00, 15.000, 3.00, 5.00, 999.00, 1, SYSDATETIME());
COMMIT;
SELECT 3 AS dirty_lines, @inv AS invoice_id;
"""

SCD2_SQL = """
SET NOCOUNT ON;
DECLARE @id int = ?;
DECLARE @newcat int = (SELECT TOP 1 CustomerCategoryID FROM Sales.CustomerCategories
                       WHERE CustomerCategoryID <> (SELECT CustomerCategoryID FROM Sales.Customers WHERE CustomerID = @id)
                       ORDER BY NEWID());
UPDATE Sales.Customers SET CustomerCategoryID = @newcat, LastEditedBy = 1 WHERE CustomerID = @id;
SELECT c.CustomerID, c.CustomerName, cc.CustomerCategoryName AS NuevaCategoria
FROM Sales.Customers c JOIN Sales.CustomerCategories cc ON cc.CustomerCategoryID = c.CustomerCategoryID WHERE c.CustomerID = @id;
"""


def simulate_days(days: int, territory: str | None, factor: float) -> None:
    with db.connection(config.DB_SOURCE) as cn:
        last = db.scalar(cn, "SELECT MAX(InvoiceDate) FROM Sales.Invoices")
        for i in range(1, days + 1):
            new_date: date = last + timedelta(days=i)
            cur = cn.cursor()
            cur.execute(COPY_DAY_SQL, new_date, new_date, territory, factor, f"SIM-{new_date:%Y%m%d}")
            res = db.last_result(cur)
            print(f"[SIMULADO] {new_date} ({new_date:%a}): {res['invoices']} facturas, {res['lines']} líneas")


def main() -> None:
    p = argparse.ArgumentParser(description="Simulación de operaciones en la fuente (identificadas como SIMULADO)")
    p.add_argument("--days", type=int, default=0)
    p.add_argument("--territory", default=None, help="Territorio de venta al que se aplica --factor")
    p.add_argument("--factor", type=float, default=1.0, help="Fracción de facturas copiadas (0.4 = caída del 60%%)")
    p.add_argument("--dirty", action="store_true")
    p.add_argument("--scd2", action="store_true")
    p.add_argument("--customer-id", type=int, default=1)
    a = p.parse_args()
    if a.days:
        simulate_days(a.days, a.territory, a.factor)
    with db.connection(config.DB_SOURCE) as cn:
        if a.dirty:
            cur = cn.cursor(); cur.execute(DIRTY_SQL)
            print("[SIMULADO] registros con problemas de calidad:", db.last_result(cur))
        if a.scd2:
            cur = cn.cursor(); cur.execute(SCD2_SQL, a.customer_id)
            print("[SIMULADO] cambio de categoría (SCD2):", db.last_result(cur))


if __name__ == "__main__":
    main()
