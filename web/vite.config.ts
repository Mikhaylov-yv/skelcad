/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Workbench SkelCAD. Сборка кладётся в пакет сервера и отдаётся FastAPI по «/».
// В разработке `npm run dev` проксирует /api и /out на локальный сервер (`uv run skelcad serve`).
const backend = process.env.SKELCAD_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/skelcad/server/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/out": backend,
      "/health": backend,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
});
