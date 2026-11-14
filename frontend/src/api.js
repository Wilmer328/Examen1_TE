// Cliente HTTP: todas las llamadas pasan por el backend con token JWT.
const TOKEN_KEY = "wwi_token";

export const auth = {
  get token() {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token, user) {
    try { sessionStorage.setItem(TOKEN_KEY, token); sessionStorage.setItem("wwi_user", JSON.stringify(user)); } catch { /* noop */ }
  },
  get user() {
    try { return JSON.parse(sessionStorage.getItem("wwi_user") || "null"); } catch { return null; }
  },
  clear() {
    try { sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem("wwi_user"); } catch { /* noop */ }
  },
};

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export async function api(path, { method = "GET", params, body, form } = {}) {
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString()
    : "";
  const headers = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  let payload;
  if (form) { payload = new URLSearchParams(form); }
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(`/api${path}${qs}`, { method, headers, body: payload });
  if (res.status === 401 && !path.startsWith("/auth")) {
    auth.clear();
    window.dispatchEvent(new Event("wwi-logout"));
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* noop */ }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export const fmtMoney = (v) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("es-EC", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
export const fmtNum = (v, d = 0) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("es-EC", { maximumFractionDigits: d, minimumFractionDigits: d });
export const fmtPct = (v) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%`);
