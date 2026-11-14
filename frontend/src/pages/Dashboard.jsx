import { useMemo, useState } from "react";
import { api, fmtMoney, fmtNum, fmtPct } from "../api.js";
import { Card, Chart, Status, chartColors, useAsync } from "../components.jsx";

const KPI_DEFS = [
  { key: "ventas_netas", label: "Ventas netas", fmt: fmtMoney, help: "Σ Quantity × UnitPrice (sin impuesto)" },
  { key: "ganancia", label: "Ganancia", fmt: fmtMoney, help: "Σ LineProfit" },
  { key: "margen_pct", label: "Margen", fmt: (v) => (v == null ? "—" : `${fmtNum(v, 1)}%`), help: "Ganancia / ventas netas (no aditivo)", pp: true },
  { key: "facturas", label: "Facturas", fmt: fmtNum, help: "Conteo distinto de InvoiceID" },
  { key: "ticket_promedio", label: "Ticket promedio", fmt: fmtMoney, help: "Ventas netas / facturas" },
  { key: "clientes_activos", label: "Clientes activos", fmt: fmtNum, help: "Clientes distintos con compras" },
];
// Jerarquías de drill-down: al hacer clic en un miembro se filtra y se baja de nivel
const DRILL = {
  territorio: { next: "estado", filter: "territorio" },
  estado: { next: "ciudad", filter: "estado" },
  categoria: { next: "producto", filter: "categoria" },
  categoria_cliente: { next: "cliente", filter: "categoria_cliente" },
};
const DIM_LABEL = { territorio: "Territorio", estado: "Estado", ciudad: "Ciudad", categoria: "Categoría", producto: "Producto",
  categoria_cliente: "Categoría de cliente", cliente: "Cliente", grupo_compra: "Grupo de compra", vendedor: "Vendedor" };

export default function Dashboard() {
  const opts = useAsync(() => api("/meta/filters"), []);
  const [f, setF] = useState({ start: "2016-01-01", end: "2016-06-07", territorio: "", categoria: "", categoria_cliente: "", grupo_compra: "" });
  const [drill, setDrill] = useState({}); // filtros extra de drill-down (estado, cliente, producto…)
  const [dim, setDim] = useState("territorio");
  const [grain, setGrain] = useState("mes");
  const [page, setPage] = useState(1);
  const params = useMemo(() => ({ ...f, ...drill }), [f, drill]);
  const key = JSON.stringify(params);

  const kpis = useAsync(() => api("/kpis", { params }), [key]);
  const trend = useAsync(() => api("/sales/trend", { params: { ...params, grain } }), [key, grain]);
  const by = useAsync(() => api("/sales/by", { params: { ...params, dimension: dim, top_n: 12 } }), [key, dim]);
  const detail = useAsync(() => api("/sales/detail", { params: { ...params, page, page_size: 15 } }), [key, page]);

  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const drillInto = (name) => {
    const d = DRILL[dim];
    if (!d || !name) return;
    if (["territorio", "categoria", "categoria_cliente"].includes(d.filter)) setF({ ...f, [d.filter]: name });
    else setDrill({ ...drill, [d.filter]: name });
    setDim(d.next); setPage(1);
  };
  const resetDrill = () => { setDrill({}); setDim("territorio"); setF({ ...f, territorio: "", categoria: "", categoria_cliente: "" }); };

  const trendOpt = useMemo(() => trend.data && {
    color: chartColors, tooltip: { trigger: "axis" }, legend: { data: ["Ventas netas", "Ganancia"] },
    grid: { left: 70, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: trend.data.map((r) => r.periodo) },
    yAxis: { type: "value", axisLabel: { formatter: (v) => `${(v / 1e6).toFixed(1)}M` } },
    series: [
      { name: "Ventas netas", type: "line", smooth: true, areaStyle: { opacity: 0.12 }, data: trend.data.map((r) => r.ventas_netas) },
      { name: "Ganancia", type: "line", smooth: true, data: trend.data.map((r) => r.ganancia) },
    ],
  }, [trend.data]);

  const byOpt = useMemo(() => by.data && {
    color: chartColors, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 160, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", axisLabel: { formatter: (v) => `${(v / 1e6).toFixed(1)}M` } },
    yAxis: { type: "category", inverse: true, data: by.data.map((r) => r.miembro), axisLabel: { width: 150, overflow: "truncate" } },
    series: [{ type: "bar", data: by.data.map((r) => r.ventas_netas), itemStyle: { borderRadius: [0, 4, 4, 0] } }],
  }, [by.data]);

  const activeDrill = Object.entries({ ...drill, ...(f.territorio && { territorio: f.territorio }), ...(f.categoria && { categoria: f.categoria }),
    ...(f.categoria_cliente && { categoria_cliente: f.categoria_cliente }) });

  return (
    <div className="page">
      <Card className="filters">
        <div className="filter-grid">
          <label>Desde<input type="date" value={f.start} onChange={set("start")} /></label>
          <label>Hasta<input type="date" value={f.end} onChange={set("end")} /></label>
          {[["territorio", "Territorio"], ["categoria", "Categoría producto"], ["categoria_cliente", "Categoría cliente"], ["grupo_compra", "Grupo de compra"]].map(([k, l]) => (
            <label key={k}>{l}
              <select value={f[k]} onChange={set(k)}>
                <option value="">Todos</option>
                {(opts.data?.[k] || []).map((o) => <option key={o}>{o}</option>)}
              </select>
            </label>
          ))}
        </div>
        {opts.data && <p className="muted small">Datos disponibles: {opts.data.rango_fechas.desde} a {opts.data.rango_fechas.hasta}. Las fechas posteriores al 2016-05-31 son operaciones SIMULADAS para la demo.</p>}
      </Card>

      <Status state={kpis}>
        {kpis.data && (
          <>
            <div className="kpis">
              {KPI_DEFS.map((k) => {
                const delta = kpis.data.variacion_pct[k.key];
                return (
                  <div className="kpi" key={k.key} title={k.help}>
                    <div className="kpi-label">{k.label}</div>
                    <div className="kpi-value">{k.fmt(kpis.data.actual[k.key])}</div>
                    <div className={`kpi-delta ${delta > 0 ? "up" : delta < 0 ? "down" : ""}`}>
                      {k.pp ? (delta == null ? "—" : `${delta > 0 ? "+" : ""}${fmtNum(delta, 1)} pp`) : fmtPct(delta)} vs período anterior
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="muted small">Período {kpis.data.periodo.desde} → {kpis.data.periodo.hasta}; comparado con {kpis.data.periodo_anterior.desde} → {kpis.data.periodo_anterior.hasta}. Fuente: {kpis.data.fuente}.</p>
          </>
        )}
      </Status>

      <div className="grid-2">
        <Card title="Tendencia histórica" actions={
          <select value={grain} onChange={(e) => setGrain(e.target.value)}>
            <option value="anio">Año</option><option value="trimestre">Trimestre</option><option value="mes">Mes</option><option value="semana">Semana</option>
          </select>}>
          <Status state={trend} empty={trend.data && !trend.data.length}><Chart option={trendOpt} /></Status>
        </Card>
        <Card title={`Ventas por ${DIM_LABEL[dim]}`} actions={
          <>
            <select value={dim} onChange={(e) => setDim(e.target.value)}>
              {Object.entries(DIM_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            {activeDrill.length > 0 && <button className="link" onClick={resetDrill}>Quitar drill-down</button>}
          </>}>
          {activeDrill.length > 0 && <div className="crumbs">Filtro: {activeDrill.map(([k, v]) => `${DIM_LABEL[k] || k}: ${v}`).join(" › ")}</div>}
          <Status state={by} empty={by.data && !by.data.length}>
            <Chart option={byOpt} onClick={DRILL[dim] ? drillInto : undefined} height={320} />
            {DRILL[dim] && <p className="muted small">Haga clic en una barra para ver el detalle por {DIM_LABEL[DRILL[dim].next]}.</p>}
          </Status>
        </Card>
      </div>

      <Card title="Detalle de líneas de venta" actions={detail.data && <span className="muted small">{fmtNum(detail.data.total)} líneas</span>}>
        <Status state={detail} empty={detail.data && !detail.data.rows.length}>
          {detail.data && (
            <>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Factura</th><th>Fecha</th><th>Cliente</th><th>Territorio</th><th>Categoría</th><th>Producto</th><th className="r">Cant.</th><th className="r">Neto</th><th className="r">Ganancia</th></tr></thead>
                  <tbody>
                    {detail.data.rows.map((r) => (
                      <tr key={r.InvoiceLineID}><td>{r.InvoiceID}</td><td>{r.InvoiceDate}</td><td>{r.CustomerName}</td><td>{r.SalesTerritory}</td>
                        <td>{r.Category}</td><td>{r.ProductName}</td><td className="r">{fmtNum(r.Quantity)}</td><td className="r">{fmtMoney(r.NetAmount)}</td><td className="r">{fmtMoney(r.LineProfit)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="pager">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Anterior</button>
                <span>Página {page} de {Math.max(1, Math.ceil(detail.data.total / detail.data.page_size))}</span>
                <button disabled={page * detail.data.page_size >= detail.data.total} onClick={() => setPage(page + 1)}>Siguiente ›</button>
              </div>
            </>
          )}
        </Status>
      </Card>
    </div>
  );
}
