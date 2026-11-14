"""Pruebas de integración del ETL: incremental, idempotencia, recuperación, reconciliación, calidad y SCD2.
Requieren SQL Server con WideWorldImporters restaurada y al menos una carga inicial."""
import pytest

from common import config, db
from etl import pipeline
from etl.catalog import ENTITIES
from etl.transformation import build_clean_sql


def _fact_snapshot(cn):
    return db.query_records(cn, "SELECT COUNT(*) AS n, SUM(NetAmount) AS net, MAX(SalesKey) AS maxkey FROM dw.FactSales")[0]


def _watermarks(cn):
    return {r["SourceObject"]: r["WatermarkValue"] for r in db.query_records(cn, "SELECT * FROM ops.Watermark")}


def test_catalog_has_rules_and_keys():
    for e in ENTITIES:
        assert e.key in e.columns and e.watermark in e.columns
        sql = build_clean_sql(e, 1)
        assert "MERGE clean." in sql and "quarantine.RejectedRecord" in sql
        for r in e.reject_rules:
            assert r.rule_id in sql


def test_incremental_is_idempotent(dw):
    before = _fact_snapshot(dw)
    eid = pipeline.run("incremental", "pytest", post_steps=False)
    assert eid > 0
    after = _fact_snapshot(dw)
    assert after == before, "Re-ejecutar sin cambios en la fuente no debe alterar el DW"
    steps = db.query_records(dw, "SELECT StepName, RowsInserted, RowsUpdated FROM ops.EtlStepLog WHERE ExecutionID = ?"
                                 " AND StepName IN ('load:dw.FactSales', 'clean:InvoiceLines')", [eid])
    assert all((s["RowsInserted"] or 0) == 0 and (s["RowsUpdated"] or 0) == 0 for s in steps)


def test_controlled_failure_does_not_advance_watermark_and_recovers(dw):
    wm_before = _watermarks(dw)
    facts_before = _fact_snapshot(dw)
    eid = pipeline.run("incremental", "pytest-falla", fail_at="load_facts", post_steps=False)
    assert eid < 0
    status = db.scalar(dw, "SELECT Status FROM ops.EtlExecution WHERE ExecutionID = ?", [-eid])
    assert status == "failed"
    assert _watermarks(dw) == wm_before, "Una ejecución fallida no debe mover los watermarks"
    eid2 = pipeline.run("incremental", "pytest-reintento", post_steps=False)
    assert eid2 > 0
    assert _fact_snapshot(dw) == facts_before


def test_reconciliation_between_layers(dw):
    rows = {r["Layer"]: r for r in db.query_records(
        dw, "SELECT Layer, RowCountValue, AmountValue FROM ops.Reconciliation WHERE ExecutionID = (SELECT MAX(ExecutionID) FROM ops.Reconciliation)")}
    assert rows["1-fuente"]["RowCountValue"] == rows["3-clean"]["RowCountValue"] + rows["3b-cuarentena"]["RowCountValue"]
    assert rows["3-clean"]["RowCountValue"] == rows["4-dw"]["RowCountValue"]
    assert abs(float(rows["3-clean"]["AmountValue"]) - float(rows["4-dw"]["AmountValue"])) < 0.01


def test_no_duplicate_grain_and_no_unknown_members(dw):
    assert db.scalar(dw, "SELECT COUNT(*) FROM (SELECT InvoiceLineID FROM dw.FactSales GROUP BY InvoiceLineID HAVING COUNT(*)>1) x") == 0
    assert db.scalar(dw, "SELECT COUNT(*) FROM dw.FactSales WHERE CustomerKey=-1 OR ProductKey=-1 OR GeographyKey=-1") == 0


def test_fact_total_matches_source_minus_quarantine(dw):
    src = db.scalar(dw, "SELECT SUM(ExtendedPrice - TaxAmount) FROM WideWorldImporters.Sales.InvoiceLines l"
                        " WHERE NOT EXISTS (SELECT 1 FROM WWI_Staging.quarantine.RejectedRecord q WHERE q.SourceObject='Sales.InvoiceLines'"
                        " AND q.Status='pendiente' AND q.BusinessKey = CAST(l.InvoiceLineID AS nvarchar(100)))")
    dwv = db.scalar(dw, "SELECT SUM(NetAmount) FROM dw.FactSales")
    assert abs(float(src) - float(dwv)) < 0.01


def test_scd2_single_current_version_and_non_overlapping(dw):
    assert db.scalar(dw, "SELECT COUNT(*) FROM (SELECT CustomerID FROM dw.DimCustomer WHERE IsCurrent=1 GROUP BY CustomerID HAVING COUNT(*)>1) x") == 0
    overlaps = db.scalar(dw, "SELECT COUNT(*) FROM dw.DimCustomer a JOIN dw.DimCustomer b ON a.CustomerID=b.CustomerID AND a.CustomerKey<b.CustomerKey"
                             " AND a.ValidFrom < b.ValidTo AND b.ValidFrom < a.ValidTo")
    assert overlaps == 0


@pytest.mark.skipif(not db.connect(config.DB_STAGING).cursor().execute(
    "SELECT COUNT(*) FROM quarantine.RejectedRecord").fetchone()[0], reason="Sin simulación de registros sucios")
def test_quarantine_and_derivation_rules_applied():
    with db.connection(config.DB_STAGING) as cn:
        rules = {r["RuleID"] for r in db.query_records(cn, "SELECT DISTINCT RuleID FROM quarantine.RejectedRecord")}
        assert {"R-IL-01", "R-IL-04"} <= rules
        derived = db.query_records(cn, "SELECT TOP 1 UnitPrice, Quantity, ExtendedPrice, TaxAmount, Description FROM clean.InvoiceLines"
                                       " WHERE IsUnitPriceDerived = 1")
        assert derived, "La línea con UnitPrice NULL debe quedar derivada y marcada"
        d = derived[0]
        assert abs(float(d["UnitPrice"]) * d["Quantity"] - (float(d["ExtendedPrice"]) - float(d["TaxAmount"]))) < 0.05
        assert "  " not in d["Description"] and d["Description"] == d["Description"].strip()
