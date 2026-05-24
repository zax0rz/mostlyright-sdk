import { defineConfig } from "tsup";

export default defineConfig([
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs", "iife"],
    globalName: "tradewindsMarkets",
    dts: true,
    sourcemap: true,
    clean: true,
    target: "es2022",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      if (format === "cjs") return { js: ".cjs" };
      return { js: ".global.js" };
    },
  },
  {
    // TS-W5 — Polymarket surface at @tradewinds/markets/polymarket. Lives
    // at the subpath (NOT root barrel) so the IIFE bundle stays light:
    // Polymarket is server-side discover/settle by design (CORS-blocked
    // from browsers per .planning/research/TS-CORS-MATRIX.md).
    entry: { index: "src/polymarket/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/polymarket",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
]);
