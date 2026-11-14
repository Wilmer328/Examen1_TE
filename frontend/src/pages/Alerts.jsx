import { useState } from "react";
import { api, auth, fmtMoney } from "../api.js";
import { Badge, Card, Status, useAsync } from "../components.jsx";

const SEV = { alta: "bad", media: "warn", baja: "ok" };

export default function Alerts() {
  const list = useAsync(() => api("/alerts", { params: { limit: 100 } }), []);
  const [sel, setSel] = useState(null);
  const deliveries = useAsync(() => (sel ? api(`/alerts/${sel.AlertID}/deliveries`) : Promise.resolve([])), [sel?.AlertID]);
  const [msg, setMsg] = useState("");
  const isAdmin = auth.user?.role === "admin";

  const setStatus = async (id, status) => {
    await api(`/alerts/${id}`, { method: "PATCH", body: { status } });
    list.reload(); if (sel?.AlertID === id) setSel({ ...sel, Status: status });
  };
  const action = async (path, label) => {
    setMsg(`${label}…`);
    try { const r = await api(path, { method: "POST" }); setMsg(`${label}: ${JSON.stringify(r)}`); list.reload(); }
    catch (e) { setMsg(`${label}: ${e.message}`); }
  };

  return (
    <div className="page">
      <Card title="Alertas" actions={isAdmin && (
        <>
          <button onClick={() => action("/alerts/evaluate", "Evaluación de reglas")}>Evaluar reglas</button>
          <button onClick={() => action("/alerts/test", "Alerta de prueba (simulada)")}>Disparar alerta de prueba</button>
        </>)}>
        {msg && <p className="muted small">{msg}</p>}
        <Status state={list} empty={list.data && !list.data.length}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Fecha/hora</th><th>Tipo</th><th>Severidad</th><th>Entidad</th><th className="r">Observado</th><th className="r">Umbral</th><th>Período</th><th>Estado</th><th></th></tr></thead>
              <tbody>
                {(list.data || []).map((a) => (
                  <tr key={a.AlertID} className={sel?.AlertID === a.AlertID ? "sel" : ""} onClick={() => setSel(a)}>
                    <td>{a.AlertID}</td><td>{a.CreatedAt.slice(0, 19)}</td>
                    <td><Badge kind={a.AlertType === "ml" ? "pred" : ""}>{a.AlertType}</Badge>{a.IsSimulated ? <Badge kind="warn">simulada</Badge> : null}</td>
                    <td><Badge kind={SEV[a.Severity]}>{a.Severity}</Badge></td><td>{a.Entity}</td>
                    <td className="r">{fmtMoney(a.ObservedValue)}</td><td className="r">{fmtMoney(a.ThresholdValue)}</td>
                    <td>{a.PeriodStart} → {a.PeriodEnd}</td><td>{a.Status}</td>
                    <td><select value={a.Status} onClick={(e) => e.stopPropagation()} onChange={(e) => setStatus(a.AlertID, e.target.value)}>
                      {["nueva", "atendida", "descartada", "resuelta"].map((s) => <option key={s}>{s}</option>)}</select></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Status>
      </Card>
      {sel && (
        <Card title={`Detalle alerta #${sel.AlertID}`}>
          <p><b>{sel.Indicator}</b> — {sel.Entity}</p>
          <p>{sel.Message}</p>
          <p className="small">Origen: {sel.Origin}{sel.ModelVersion ? ` · modelo ${sel.ModelVersion}` : ""} · referencia {fmtMoney(sel.ReferenceValue)}</p>
          {sel.RecommendedAction && <p className="small"><b>Acción recomendada:</b> {sel.RecommendedAction}</p>}
          {sel.Explanation && <div className="ai-box"><Badge kind="ia">Explicación generada por IA — verificar</Badge><p>{sel.Explanation}</p></div>}
          <h4>Entregas</h4>
          <Status state={deliveries} empty={deliveries.data && !deliveries.data.length}>
            <ul className="small">{(deliveries.data || []).map((d) => <li key={d.Channel}><b>{d.Channel}</b>: {d.Status} · intentos {d.Attempts} · {d.Detail || d.LastError}</li>)}</ul>
          </Status>
        </Card>
      )}
    </div>
  );
}
