import path from "path";
import { defineConfig } from "vitest/config";
import { readFileSync } from "fs";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

export default defineConfig({
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
      "react/jsx-dev-runtime": path.resolve(__dirname, "node_modules/react/jsx-dev-runtime"),
      "react/jsx-runtime": path.resolve(__dirname, "node_modules/react/jsx-runtime"),
    },
  },
  server: {
    fs: {
      allow: [".", "../games/games"],
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: [path.resolve(__dirname, "src/test-setup.ts")],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    pool: "threads",
    forceExit: true,
  },
});
