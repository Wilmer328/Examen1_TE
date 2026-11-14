import { useState } from "react";
import { api, auth, fmtMoney, fmtNum } from "../api.js";
import { Badge, Card, Status, useAsync } from "../components.jsx";

export default function Ops() {
  const s = useAsync(() => api("/ops/summary"), []);
  const [run, setRun] = useState(null);
  const steps = useAsync(() => (run ? api(`/ops/runs/${run}`) : Promise.resolve([])), [run]);
  const [msg, setMsg] = useState("");
  const d = s.data;

  const launch = async () => {
    setMsg("Lanzando pipeline…");
    try { await api("/ops/run-pipeline", { method: "POST" }); setMsg("Pipeline lanzado. Actualice en unos segundos."); }
    catch (e) { setMsg(e.message); }
  };

  return (
    <div className="page">
      <Status state={s}>
        {d && (
          <>
            <div className="kpis">
              <div className="kpi"><div className="kpi-label">Última carga exitosa</div><div className="kpi-value sm">{d.ultima_exitosa ? String(d.ultima_exitosa.EndTime).slice(0, 19) : "—"}</div>
                <div className="kpi-delta">Ejecución #{d.ultima_exitosa?.ExecutionID} · {d.ultima_exitosa?.Mode}</div></div>
              <div className="kpi"><div className="kpi-label">Reglas de calidad OK</div><div className="kpi-value">{d.calidad.filter((q) => q.Passed).length}/{d.calidad.length}</div></div>
              <div className="kpi"><div className="kpi-label">Modelo activo</div><div className="kpi-value sm">{d.modelo_activo?.ModelVersion || "—"}</div><div className="kpi-delta">{d.modelo_activo?.Algorithm}</div></div>
              <div className="kpi"><div className="kpi-label">Notificaciones</div><div className="kpi-value sm">{d.notificaciones.map((n) => `${n.Channel} ${n.Status}: ${n.n}`).join(" · ") || "—"}</div></div>
              <div className="kpi"><div className="kpi-label">Asistente IA</div><div className="kpi-value sm">{d.asistente?.consultas ?? 0} consultas</div><div className="kpi-delta">{d.asistente?.exitosas ?? 0} ok · {fmtNum(d.asistente?.latencia_prom_ms)} ms prom.</div></div>
            </div>

            <Card title="Ejecuciones ETL" actions={<>{auth.user?.role === "admin" && <button onClick={launch}>Ejecutar pipeline</button>}<button onClick={s.reload}>Actualizar</button></>}>
              {msg && <p className="muted small">{msg}</p>}
              <div className="table-wrap"><table>
                <thead><tr><th>#</th><th>Modo</th><th>Origen</th><th>Inicio</th><th className="r">Duración</th><th>Estado</th><th className="r">Extraídas</th><th className="r">Rechazadas</th><th className="r">Hechos insertados</th><th>Error</th></tr></thead>
                <tbody>{d.ejecuciones.map((r) => (
                  <tr key={r.ExecutionID} className={run === r.ExecutionID ? "sel" : ""} onClick={() => setRun(r.ExecutionID)}>
                    <td>{r.ExecutionID}</td><td>{r.Mode}</td><td>{r.TriggeredBy}</td><td>{String(r.StartTime).slice(0, 19)}</td><td className="r">{r.DurationSec ?? "—"} s</td>
                    <td><Badge kind={r.Status === "success" ? "ok" : r.Status === "failed" ? "bad" : "warn"}>{r.Status}</Badge></td>
                    <td className="r">{fmtNum(r.RowsExtracted)}</td><td className="r">{fmtNum(r.RowsRejected)}</td><td className="r">{fmtNum(r.FactsInserted)}</td><td className="small">{r.ErrorDetail}</td></tr>))}
                </tbody></table></div>
              <p className="muted small">Haga clic en una ejecución para ver sus pasos (auditoría: conteos leídos/insertados/actualizados/rechazados y watermarks).</p>
            </Card>

            {run && (
              <Card title={`Pasos de la ejecución #${run}`}>
                <Status state={steps}><div className="table-wrap"><table>
                  <thead><tr><th>Paso</th><th>Origen</th><th>Destino</th><th className="r">Leídas</th><th className="r">Ins.</th><th className="r">Act.</th><th className="r">Rech.</th><th>Watermark</th><th>Estado</th></tr></thead>
                  <tbody>{(steps.data || []).map((x, i) => (
                    <tr key={i}><td>{x.StepName}</td><td className="small">{x.SourceObject}</td><td className="small">{x.TargetObject}</td><td className="r">{fmtNum(x.RowsRead)}</td>
                      <td className="r">{fmtNum(x.RowsInserted)}</td><td className="r">{fmtNum(x.RowsUpdated)}</td><td className="r">{fmtNum(x.RowsRejected)}</td>
                      <td className="small">{x.WatermarkEnd ? `${String(x.WatermarkStart || "inicio").slice(0, 19)} → ${String(x.WatermarkEnd).slice(0, 19)}` : ""}</td><td>{x.Status}</td></tr>))}
                  </tbody></table></div></Status>
              </Card>
            )}

            <div className="grid-2">
              <Card title="Calidad de datos (última ejecución)">
                <div className="table-wrap"><table>
                  <thead><tr><th>Regla</th><th>Dimensión</th><th>Descripción</th><th className="r">Valor</th><th className="r">Umbral</th><th></th></tr></thead>
                  <tbody>{d.calidad.map((q) => (<tr key={q.RuleID}><td>{q.RuleID}</td><td>{q.QualityDimension}</td><td className="small">{q.Description}</td>
                    <td className="r">{fmtNum(q.MetricValue, 2)}</td><td className="r">{fmtNum(q.Threshold)}</td><td><Badge kind={q.Passed ? "ok" : "bad"}>{q.Passed ? "OK" : "Revisar"}</Badge></td></tr>))}</tbody>
                </table></div>
              </Card>
              <Card title="Reconciliación entre capas (líneas de factura)">
                <div className="table-wrap"><table>
                  <thead><tr><th>Capa</th><th>Objeto</th><th className="r">Filas</th><th className="r">Monto neto</th></tr></thead>
                  <tbody>{d.reconciliacion.map((r) => (<tr key={r.Layer}><td>{r.Layer}</td><td className="small">{r.ObjectName}</td><td className="r">{fmtNum(r.RowCountValue)}</td><td className="r">{fmtMoney(r.AmountValue)}</td></tr>))}</tbody>
                </table></div>
                <p className="muted small">Regla: fuente = clean + cuarentena pendiente; clean = DW.</p>
              </Card>
            </div>
            <div className="grid-2">
              <Card title="Cuarentena (registros rechazados)">
                <Status state={s} empty={!d.cuarentena.length}><div className="table-wrap"><table>
                  <thead><tr><th>Ejec.</th><th>Objeto</th><th>Clave</th><th>Regla</th><th>Estado</th></tr></thead>
                  <tbody>{d.cuarentena.map((q) => (<tr key={q.RejectedID}><td>{q.ExecutionID}</td><td>{q.SourceObject}</td><td>{q.BusinessKey}</td><td className="small">{q.RuleID} {q.RuleDescription}</td><td>{q.Status}</td></tr>))}</tbody>
                </table></div></Status>
              </Card>
              <Card title="Watermarks de carga incremental">
                <div className="table-wrap"><table>
                  <thead><tr><th>Objeto fuente</th><th>Columna</th><th>Valor</th></tr></thead>
                  <tbody>{d.watermarks.map((w) => (<tr key={w.SourceObject}><td>{w.SourceObject}</td><td>{w.WatermarkColumn}</td><td className="small">{String(w.WatermarkValue).slice(0, 23)}</td></tr>))}</tbody>
                </table></div>
              </Card>
            </div>
          </>
        )}
      </Status>
    </div>
  );
}
