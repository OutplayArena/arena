import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { readFileSync } from "fs";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  resolve: {
    alias: {
      "@games": path.resolve(__dirname, "../games/games"),
      "@frontend": path.resolve(__dirname, "src"),
      "react": path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
      "react-router-dom": path.resolve(__dirname, "node_modules/react-router-dom"),
    },
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    // Accept any Host header (so the dev server is reachable from Tailscale
    // MagicDNS names, LAN IPs, etc.). Safe for local dev only — set to a
    // specific list in production.
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.ARENA_API_TARGET ?? "http://localhost:8000",
        changeOrigin: false,
      },
      // Proxy /docs to the backend which serves mkdocs output as static files
      // from backend/static/docs/. Run `mkdocs build` once into that directory
      // before starting the dev server, or set ARENA_DOCS_TARGET to a running
      // mkdocs serve instance (e.g. http://localhost:8080) and set
      // ARENA_DOCS_REWRITE=1 to strip the /docs prefix for that target.
      "/docs": {
        target: process.env.ARENA_DOCS_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        ...(process.env.ARENA_DOCS_REWRITE
          ? { rewrite: (path: string) => path.replace(/^\/docs\/?/, "/") || "/" }
          : {}),
      },
    },
    fs: {
      allow: ["..", "../games/games"],
    },
  },
});
