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
    proxy: {
      "/api": "http://localhost:8000",
    },
    fs: {
      allow: ["..", "../games/games"],
    },
  },
});
