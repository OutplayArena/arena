import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@games": path.resolve(__dirname, "../games"),
      "@frontend": path.resolve(__dirname, "src"),
      "react": path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
      "react-router-dom": path.resolve(__dirname, "node_modules/react-router-dom"),
      "react/jsx-dev-runtime": path.resolve(__dirname, "node_modules/react/jsx-dev-runtime"),
      "react/jsx-runtime": path.resolve(__dirname, "node_modules/react/jsx-runtime"),
    },
  },
  server: {
    fs: {
      allow: [".", "../games"],
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: [path.resolve(__dirname, "src/test-setup.ts")],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
