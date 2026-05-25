import { defineConfig } from "tsup";

export default defineConfig([
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs", "iife"],
    globalName: "mostlyrightMarkets",
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
    // TS-W5 — Polymarket surface at @mostlyright/markets/polymarket. Lives
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
  {
    // Phase 9 — trade-history surface at @mostlyright/markets/trades.
    // Same subpath rationale as Polymarket: trades endpoints (Kalshi
    // /trade-api/v2 + Polymarket Gamma) are server-side by design for
    // Node + Workers, kept out of the IIFE root bundle to preserve
    // browser-bundle size targets.
    entry: { index: "src/trades/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/trades",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
]);
