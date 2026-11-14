"""Dashboard/API: seguridad y KPIs contrastados contra consultas SQL INDEPENDIENTES (sobre FactSales + dimensiones,
no sobre la vista que usa la API)."""
from common import db

INDEP = """
SELECT SUM(f.NetAmount) net, SUM(f.LineProfit) profit, COUNT(DISTINCT f.InvoiceID) inv, SUM(f.Quantity) qty,
       COUNT(DISTINCT c.CustomerID) cust
FROM dw.FactSales f JOIN dw.DimDate d ON d.DateKey = f.DateKey
JOIN dw.DimGeography g ON g.GeographyKey = f.GeographyKey JOIN dw.DimProduct p ON p.ProductKey = f.ProductKey
JOIN dw.DimCustomer c ON c.CustomerKey = f.CustomerKey
WHERE d.[Date] BETWEEN ? AND ? {extra}
"""


def test_requires_authentication(client):
    assert client.get("/api/kpis").status_code == 401
    assert client.get("/api/kpis", headers={"Authorization": "Bearer x.y.z"}).status_code == 401


def test_wrong_password_rejected(client):
    assert client.post("/api/auth/login", data={"username": "admin", "password": "mal"}).status_code == 401


def test_kpis_match_independent_sql(client, auth, dw):
    r = client.get("/api/kpis", params={"start": "2015-01-01", "end": "2015-12-31"}, headers=auth).json()["actual"]
    e = db.query_records(dw, INDEP.format(extra=""), ["2015-01-01", "2015-12-31"])[0]
    assert abs(r["ventas_netas"] - float(e["net"])) < 0.01
    assert abs(r["ganancia"] - float(e["profit"])) < 0.01
    assert r["facturas"] == e["inv"] and r["unidades"] == e["qty"] and r["clientes_activos"] == e["cust"]


def test_combined_filters_match_independent_sql(client, auth, dw):
    params = {"start": "2016-01-01", "end": "2016-03-31", "territorio": "Southeast", "categoria": "Clothing"}
    r = client.get("/api/kpis", params=params, headers=auth).json()["actual"]
    e = db.query_records(dw, INDEP.format(extra="AND g.SalesTerritory = ? AND p.Category = ?"),
                         ["2016-01-01", "2016-03-31", "Southeast", "Clothing"])[0]
    assert abs(r["ventas_netas"] - float(e["net"] or 0)) < 0.01


def test_breakdown_totals_not_duplicated_by_joins(client, auth, dw):
    rows = client.get("/api/sales/by", params={"dimension": "territorio", "top_n": 50, "start": "2014-01-01",
                                               "end": "2014-12-31"}, headers=auth).json()
    total = sum(x["ventas_netas"] for x in rows)
    e = db.query_records(dw, INDEP.format(extra=""), ["2014-01-01", "2014-12-31"])[0]
    assert abs(total - float(e["net"])) < 0.05


def test_period_without_data_returns_zero(client, auth):
    r = client.get("/api/kpis", params={"start": "2030-01-01", "end": "2030-01-31"}, headers=auth).json()
    assert r["actual"]["ventas_netas"] == 0 and r["actual"]["facturas"] == 0


def test_invalid_inputs_rejected(client, auth):
    assert client.get("/api/sales/by", params={"dimension": "1;DROP TABLE x"}, headers=auth).status_code == 422
    assert client.get("/api/kpis", params={"start": "2016-02-01", "end": "2016-01-01"}, headers=auth).status_code == 422
    assert client.get("/api/sales/detail", params={"page_size": 5000}, headers=auth).status_code == 422


def test_detail_pagination(client, auth):
    r = client.get("/api/sales/detail", params={"page": 2, "page_size": 10}, headers=auth).json()
    assert r["total"] > 20 and len(r["rows"]) == 10 and r["page"] == 2


def test_freshness_and_no_credentials_exposed(client, auth):
    r = client.get("/api/meta/freshness", headers=auth)
    assert r.status_code == 200 and r.json()["ultima_carga_exitosa"] is not None
    assert "PWD" not in r.text and "password" not in r.text.lower()


def test_admin_endpoints_forbidden_for_analyst(client, auth):
    assert client.post("/api/ops/run-pipeline", headers=auth).status_code == 403
