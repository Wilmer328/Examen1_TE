import { useMemo, useState } from "react";
import { api, fmtMoney, fmtNum } from "../api.js";
import { Badge, Card, Chart, Status, chartColors, useAsync } from "../components.jsx";

export default function Forecast() {
  const models = useAsync(() => api("/ml/models"), []);
  const fc = useAsync(() => api("/ml/forecast"), []);
  const [terr, setTerr] = useState("Southeast");
  const bt = useAsync(() => api("/ml/backtest", { params: { territorio: terr } }), [terr]);
  const active = models.data?.find((m) => m.IsActive);
  const territories = [...new Set((fc.data?.predicciones || []).map((p) => p.SalesTerritory))];

  const btOpt = useMemo(() => bt.data && {
    color: [chartColors[0], chartColors[2], "#9aa5b5"], tooltip: { trigger: "axis" },
    legend: { data: ["Real", "Predicción (h=1)", "Baseline"] }, grid: { left: 70, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: bt.data.map((r) => r.WeekStart) },
    yAxis: { type: "value", axisLabel: { formatter: (v) => `${(v / 1e3).toFixed(0)}k` } },
    series: [
      { name: "Real", type: "line", data: bt.data.map((r) => r.ActualNetAmount) },
      { name: "Predicción (h=1)", type: "line", lineStyle: { type: "dashed" }, data: bt.data.map((r) => r.PredictedNetAmount) },
      { name: "Baseline", type: "line", lineStyle: { type: "dotted" }, data: bt.data.map((r) => r.BaselineNetAmount) },
    ],
  }, [bt.data]);

  const rows = active ? Object.entries(active.metrics.horizons) : [];
  return (
    <div className="page">
      <Card title="Modelo activo" actions={<Badge kind="pred">PREDICCIÓN</Badge>}>
        <Status state={models} empty={models.data && !active}>
          {active && (
            <>
              <p><b>{active.ModelVersion}</b> · {active.Algorithm} · entrenado {String(active.TrainedAt).slice(0, 16)}</p>
              <p className="muted small">Problema: {active.metrics.problem}. División temporal: entrenamiento hasta {active.TrainEnd},
                validación {active.ValidStart} → {active.ValidEnd}, prueba {active.TestStart} → {active.TestEnd}. El conjunto de prueba
                no se usó para seleccionar el modelo.</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Horizonte</th><th className="r">MAE modelo</th><th className="r">MAE media móvil 4</th><th className="r">MAE naive estacional</th><th className="r">MAE última semana</th><th className="r">sMAPE modelo</th><th className="r">Mejora vs mejor baseline</th></tr></thead>
                  <tbody>
                    {rows.map(([h, r]) => (
                      <tr key={h}><td>{h} semana(s)</td><td className="r">{fmtMoney(r.model.MAE)}</td><td className="r">{fmtMoney(r.media_movil_4.MAE)}</td>
                        <td className="r">{fmtMoney(r.naive_estacional_52.MAE)}</td><td className="r">{fmtMoney(r.naive_ultima_semana.MAE)}</td>
                        <td className="r">{fmtNum(r.model["sMAPE_%"], 1)}%</td><td className="r">{fmtNum(r["improvement_vs_best_baseline_%"], 1)}%</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Status>
      </Card>

      <div className="grid-2">
        <Card title="Backtest en prueba: real vs predicción" actions={
          <select value={terr} onChange={(e) => setTerr(e.target.value)}>{territories.map((t) => <option key={t}>{t}</option>)}</select>}>
          <Status state={bt} empty={bt.data && !bt.data.length}><Chart option={btOpt} /></Status>
        </Card>
        <Card title="Pronóstico próximas 4 semanas" actions={<Badge kind="pred">PREDICCIÓN · no es dato histórico</Badge>}>
          <Status state={fc} empty={fc.data && !fc.data.predicciones.length}>
            {fc.data && (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Territorio</th><th>Semana objetivo</th><th>h</th><th className="r">Ventas netas pronosticadas</th></tr></thead>
                  <tbody>
                    {fc.data.predicciones.filter((p) => p.SalesTerritory === terr).map((p) => (
                      <tr key={p.TargetWeekStart}><td>{p.SalesTerritory}</td><td>{p.TargetWeekStart}</td><td>{p.HorizonWeeks}</td><td className="r">{fmtMoney(p.PredictedNetAmount)}</td></tr>
                    ))}
                  </tbody>
                </table>
                <p className="muted small">Origen: semana {fc.data.predicciones[0]?.AsOfWeek}. Modelo {fc.data.modelo?.version}. Generado {String(fc.data.predicciones[0]?.PredictionDate).slice(0, 16)}.</p>
              </div>
            )}
          </Status>
        </Card>
      </div>
    </div>
  );
}
