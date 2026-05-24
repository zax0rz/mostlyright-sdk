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
    // TS-W4 Plan 02 — temporal transforms (lag, diff, diff2, rolling).
    // Emitted at @tradewinds/core/transforms. Pure row→row functions; live
    // at the subpath (NOT root barrel) so the @tradewinds/core main bundle
    // stays under its 25 KB size-limit gate (iter-4 H8 lesson). Wave 3+4
    // (calendar features, cross-features) will APPEND to this barrel in
    // subsequent plans.
    entry: { index: "src/transforms/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/transforms",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W4 Plan 05 — QC engine + 5 alpha rules. Bit positions sourced
    // from data/generated/qc-alpha-rules.ts (codegen). Emitted at
    // @tradewinds/core/qc. Lives at subpath (NOT root barrel) to keep the
    // @tradewinds/core main bundle under its 25 KB size-limit gate
    // (TS-BUNDLE-01); same pattern as transforms / temporal / formats.
    entry: { index: "src/qc/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/qc",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // Iter-4 H8 — validateRows moved out of the main barrel to keep
    // @tradewinds/core's main bundle under its 25 KB size-limit gate
    // (TS-BUNDLE-01). Emitted at @tradewinds/core/validator.
    entry: { validator: "src/validator.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // TS-W3 Plan 01-03 — cache subsystem (CacheStore, MemoryStore, FsStore,
    // IndexedDBStore [plan 02], defaultCacheStore [plan 02], skip-rules + keys
    // [plan 03]). Emitted at @tradewinds/core/internal/cache.
    //
    // Iter-8 H15: TWO entries — Node (`index.ts`, keeps the dynamic
    // FsStore import) and browser (`index.browser.ts`, NO reference to
    // FsStore via any mechanism). package.json conditional exports route
    // Node consumers to `index.mjs` and browser/MV3 consumers to
    // `index.browser.mjs`, eliminating the Node-only-deps edge that
    // breaks `pnpm size` for the meta bundle.
    entry: {
      "cache/index": "src/internal/cache/index.ts",
      "cache/index.browser": "src/internal/cache/index.browser.ts",
    },
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
    // Iter-2 H5: dedicated Node-only subpath for FsStore. The cache
    // barrel (above) intentionally does NOT re-export FsStore /
    // defaultFsRoot because tsup hoists them into a sibling chunk
    // that the browser-facing subbundle then top-level-imports
    // (pulling node:fs/promises, node:os, node:path, node:crypto,
    // proper-lockfile into MV3 bundles). FsStore consumers must
    // import from this subpath, NOT from `@tradewinds/core/internal/
    // cache`. Emitted at `@tradewinds/core/internal/cache/fs`.
    entry: { "cache/fs": "src/internal/cache/fs-entry.ts" },
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
