import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  base: command === "serve" ? "/" : "/static/",
  server: {
    host: "0.0.0.0",
    port: 8000,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.EVENTPASS_API_PROXY_TARGET || "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../../backend/static",
    emptyOutDir: true,
  },
}));
