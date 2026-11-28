import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ command, mode }) => {
  const fastApiStaticBuild = mode === "fastapi";

  return {
    plugins: [react(), tailwindcss()],
    base: command === "serve" || !fastApiStaticBuild ? "/" : "/static/",
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
      outDir: fastApiStaticBuild ? "../../backend/static" : "dist",
      emptyOutDir: true,
    },
  };
});
