import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
    },
    fs: {
      allow: ["..", "../games/games"],
    },
  },
});
