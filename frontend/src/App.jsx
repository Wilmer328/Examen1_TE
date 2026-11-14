import { useEffect, useState } from "react";
import { api, auth } from "./api.js";
import { useAsync } from "./components.jsx";
import Alerts from "./pages/Alerts.jsx";
import Assistant from "./pages/Assistant.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Forecast from "./pages/Forecast.jsx";
import Ops from "./pages/Ops.jsx";

const TABS = [
  ["dashboard", "Dashboard", Dashboard],
  ["forecast", "Predicciones", Forecast],
  ["assistant", "Asistente IA", Assistant],
  ["alerts", "Alertas", Alerts],
  ["ops", "Operación", Ops],
];

function Login({ onLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try {
      const r = await api("/auth/login", { method: "POST", form: { username: u, password: p } });
      auth.set(r.access_token, r.user); onLogin(r.user);
    } catch (ex) { setErr(ex.message); }
  };
  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <h2>Plataforma de Datos WWI</h2>
        <p className="muted">Ingeniería de datos · BI · ML · IA generativa</p>
        <label>Usuario<input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" /></label>
        <label>Contraseña<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
        {err && <div className="status error">{err}</div>}
        <button disabled={!u || !p}>Ingresar</button>
      </form>
    </div>
  );
}

function Shell({ user, onLogout }) {
  const [tab, setTab] = useState(() => { try { return localStorage.getItem("wwi_tab") || "dashboard"; } catch { return "dashboard"; } });
  const [toasts, setToasts] = useState([]);
  const fresh = useAsync(() => api("/meta/freshness"), []);

  useEffect(() => { try { localStorage.setItem("wwi_tab", tab); } catch { /* noop */ } }, [tab]);
  // WebSocket: alertas nuevas aparecen como notificación inmediata
  useEffect(() => {
    let ws; let closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws/alerts?token=${encodeURIComponent(auth.token)}`);
      ws.onmessage = (ev) => {
        const a = JSON.parse(ev.data);
        setToasts((t) => [...t, a].slice(-4));
        setTimeout(() => setToasts((t) => t.filter((x) => x.AlertID !== a.AlertID)), 15000);
      };
      ws.onclose = () => { if (!closed) setTimeout(connect, 5000); };
    };
    connect();
    return () => { closed = true; ws && ws.close(); };
  }, []);

  const Page = TABS.find((t) => t[0] === tab)[2];
  const last = fresh.data?.ultima_carga_exitosa;
  return (
    <>
      <header className="top">
        <div className="brand">WWI · Plataforma de Datos</div>
        <nav>{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>)}</nav>
        <div className="who">
          <span className="small muted" title="Hora de la última carga ETL exitosa">
            Datos actualizados: {last ? String(last.EndTime).slice(0, 16).replace("T", " ") : "—"} (hasta {fresh.data?.datos?.hasta || "—"})
          </span>
          <span className="small">{user.username} ({user.role})</span>
          <button className="link" onClick={onLogout}>Salir</button>
        </div>
      </header>
      <main><Page /></main>
      <div className="toasts">
        {toasts.map((a) => (
          <div key={a.AlertID} className={`toast sev-${a.Severity}`} onClick={() => setTab("alerts")}>
            <b>Nueva alerta #{a.AlertID} ({a.Severity}{a.IsSimulated ? ", simulada" : ""})</b>
            <div className="small">{a.Message}</div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(auth.token ? auth.user : null);
  useEffect(() => {
    const h = () => setUser(null);
    window.addEventListener("wwi-logout", h);
    return () => window.removeEventListener("wwi-logout", h);
  }, []);
  if (!user) return <Login onLogin={setUser} />;
  return <Shell user={user} onLogout={() => { auth.clear(); setUser(null); }} />;
}
