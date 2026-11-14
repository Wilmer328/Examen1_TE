import { useState } from "react";
import { api } from "../api.js";
import { Badge, Card, useAsync } from "../components.jsx";

const SAMPLES = [
  "¿Cuáles fueron las ventas del último trimestre completo?",
  "¿Qué categorías tuvieron mayor crecimiento en 2016-Q1 frente a 2015-Q1?",
  "¿Qué territorios presentan una disminución relevante en el último mes?",
  "Explica el margen de 2015 y qué datos lo respaldan.",
  "¿Cuál es el pronóstico de ventas para Southeast?",
  "¿Cuántos empleados tiene la empresa en Europa?",
];

// Resalta las etiquetas [DATO] / [PREDICCIÓN] / [INTERPRETACIÓN] que el asistente debe usar
function Rich({ text }) {
  const parts = text.split(/(\[DATO\]|\[PREDICCIÓN\]|\[INTERPRETACIÓN\])/g);
  return <div className="answer">{parts.map((p, i) =>
    p === "[DATO]" ? <Badge key={i} kind="ok">DATO</Badge> : p === "[PREDICCIÓN]" ? <Badge key={i} kind="pred">PREDICCIÓN</Badge>
      : p === "[INTERPRETACIÓN]" ? <Badge key={i} kind="ia">INTERPRETACIÓN</Badge> : <span key={i}>{p}</span>)}</div>;
}

export default function Assistant() {
  const status = useAsync(() => api("/assistant/status"), []);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState([]);

  const ask = async (text) => {
    const pregunta = (text ?? q).trim();
    if (!pregunta || busy) return;
    setBusy(true); setQ("");
    setChat((c) => [...c, { role: "user", text: pregunta }]);
    try {
      const r = await api("/assistant/ask", { method: "POST", body: { pregunta } });
      setChat((c) => [...c, { role: "bot", r }]);
    } catch (e) {
      setChat((c) => [...c, { role: "err", text: e.message }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <Card title="Asistente analítico (IA generativa)" actions={<Badge kind="ia">Respuestas generadas por IA</Badge>}>
        {status.data && !status.data.configurado && (
          <div className="status error">
            El asistente no está disponible ({status.data.proveedor}): {status.data.detalle || "revise la configuración del proveedor de IA en el .env del backend."}
          </div>
        )}
        <p className="muted small">El asistente solo consulta el Data Warehouse mediante herramientas analíticas aprobadas (sin SQL libre). Cada respuesta indica las consultas usadas
          y una verificación automática de cifras (heurística: revise siempre las fuentes).
          Proveedor: {status.data?.proveedor ?? "—"} · Modelo: {status.data?.modelo ?? "—"}.</p>
        <div className="samples">{SAMPLES.map((s) => <button key={s} className="chip" onClick={() => ask(s)} disabled={busy}>{s}</button>)}</div>
        <div className="chat">
          {chat.map((m, i) => m.role === "user" ? <div key={i} className="msg user">{m.text}</div>
            : m.role === "err" ? <div key={i} className="msg err">⚠ {m.text}</div>
              : (
                <div key={i} className="msg bot">
                  <Rich text={m.r.respuesta} />
                  <details>
                    <summary>Fuentes: {m.r.herramientas_usadas.length} consulta(s) al DW · {m.r.latencia_ms} ms · datos hasta {m.r.datos_actualizados?.datos?.hasta}</summary>
                    <ul className="small">{m.r.herramientas_usadas.map((t, j) => <li key={j}><code>{t.herramienta}</code> {JSON.stringify(t.parametros)} {t.error ? `→ error: ${t.error}` : `→ ${t.filas} fila(s)`}</li>)}</ul>
                    <p className="muted small">{m.r.aviso} Modelo {m.r.modelo}.</p>
                  </details>
                </div>
              ))}
          {busy && <div className="msg bot muted">Consultando el Data Warehouse…</div>}
        </div>
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(); }}>
          <input value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder="Escriba una pregunta sobre ventas, clientes, productos, territorios…" />
          <button disabled={busy || !q.trim()}>Preguntar</button>
        </form>
      </Card>
    </div>
  );
}
