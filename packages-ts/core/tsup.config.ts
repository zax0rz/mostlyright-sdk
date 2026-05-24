import { defineConfig } from "tsup";

// Two builds:
//   - Main: src/index.ts emitted as ESM + CJS + IIFE.
//   - Subpath: src/internal/{bounds,convert}.ts emitted as ESM + CJS only
//     (no IIFE — internal helpers are not a browser global surface).
// The subpath build is invoked via `exports["./internal/..."]` in
// package.json so weather/markets/meta can import the canonical
// constants instead of duplicating them. See TS-W1 iter-1 HIGH 3.
export default defineConfig([
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs", "iife"],
    globalName: "tradewindsCore",
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
    // TS-W2 Plan 05 — pairs join (Mode 1; forecast-less buildPairs).
    entry: ["src/internal/bounds.ts", "src/internal/convert.ts", "src/internal/pairs.ts"],
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/internal",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W2 Plan 04 — multi-source merge policies.
    entry: { "merge/index": "src/internal/merge/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/internal",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W3 Plan 04 — temporal primitives (TimePoint, KnowledgeView,
    // LeakageDetector, assertNoLeakage). Emitted at @tradewinds/core/temporal.
    entry: { index: "src/temporal/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/temporal",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W3 Plan 07 — JSON/CSV/TOON serializers. Emitted at
    // @tradewinds/core/formats. Parquet + DataFrame deferred (no stubs).
    entry: { index: "src/formats/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/formats",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W3 Plan 01-03 — cache subsystem (CacheStore, MemoryStore, FsStore,
    // IndexedDBStore [plan 02], defaultCacheStore [plan 02], skip-rules + keys
    // [plan 03]). Emitted at @tradewinds/core/internal/cache.
    entry: { "cache/index": "src/internal/cache/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/internal",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
]);
