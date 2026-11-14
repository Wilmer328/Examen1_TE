import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, /api y /ws se redirigen al backend FastAPI: el navegador nunca habla con SQL Server.
const API = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": API,
      "/ws": { target: API.replace("http", "ws"), ws: true },
    },
  },
});
