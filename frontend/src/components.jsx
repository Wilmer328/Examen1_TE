import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";

// Gráfico ECharts reutilizable. onClick recibe el nombre de la categoría (para drill-down).
export function Chart({ option, height = 300, onClick }) {
  const el = useRef(null);
  const inst = useRef(null);
  useEffect(() => {
    inst.current = echarts.init(el.current);
    const ro = new ResizeObserver(() => inst.current && inst.current.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); inst.current.dispose(); };
  }, []);
  useEffect(() => { inst.current && inst.current.setOption(option, true); }, [option]);
  useEffect(() => {
    if (!inst.current) return;
    inst.current.off("click");
    if (onClick) inst.current.on("click", (p) => onClick(p.name));
  }, [onClick]);
  return <div ref={el} style={{ width: "100%", height }} />;
}

export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((error) => alive && setState({ loading: false, error, data: null }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

// Estados de carga / error / sin datos
export function Status({ state, empty, children }) {
  if (state.loading && !state.data) return <div className="status">Cargando…</div>;
  if (state.error) return <div className="status error">⚠ {state.error.message} <button className="link" onClick={state.reload}>Reintentar</button></div>;
  if (empty) return <div className="status">Sin datos para los filtros seleccionados.</div>;
  return children;
}

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && <header className="card-h"><h3>{title}</h3><div className="actions">{actions}</div></header>}
      {children}
    </section>
  );
}

export function Badge({ kind, children }) {
  return <span className={`badge ${kind || ""}`}>{children}</span>;
}

export const chartColors = ["#2a6fdb", "#12a37f", "#e08a1e", "#8a5cd8", "#d64e6a", "#3aa6b9", "#7d8a20", "#b0603a", "#5b6b84"];
