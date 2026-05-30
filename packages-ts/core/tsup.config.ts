import { defineConfig } from "tsup";

// Two builds:
//   - Main: src/index.ts emitted as ESM + CJS + IIFE.
//   - Subpath: src/internal/{bounds,convert}.ts emitted as ESM + CJS only
//     (no IIFE — internal helpers are not a browser global surface).
// The subpath build is invoked via `exports["./internal/..."]` in
// package.json so weather/markets/meta can import the canonical
// constants instead of duplicating them. See TS-W1 iter-1 HIGH 3.
const allConfigs = [
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs", "iife"],
    globalName: "mostlyrightCore",
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
    // LeakageDetector, assertNoLeakage). Emitted at @mostlyrightmd/core/temporal.
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
    // @mostlyrightmd/core/formats. Parquet + DataFrame deferred (no stubs).
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
    // Emitted at @mostlyrightmd/core/transforms. Pure row→row functions; live
    // at the subpath (NOT root barrel) so the @mostlyrightmd/core main bundle
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
    // @mostlyrightmd/core/qc. Lives at subpath (NOT root barrel) to keep the
    // @mostlyrightmd/core main bundle under its 25 KB size-limit gate
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
    // @mostlyrightmd/core's main bundle under its 25 KB size-limit gate
    // (TS-BUNDLE-01). Emitted at @mostlyrightmd/core/validator.
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
    // [plan 03]). Emitted at @mostlyrightmd/core/internal/cache.
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
    // import from this subpath, NOT from `@mostlyrightmd/core/internal/
    // cache`. Emitted at `@mostlyrightmd/core/internal/cache/fs`.
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
  {
    // TS-W6 — discovery surface (availability, internationalDailyExtremes,
    // buildSnapshot/DataSnapshot, dataVersionFromComponents/forResearch,
    // describe/featureCatalog/climateGaps). Emitted at
    // @mostlyrightmd/core/discovery. Lives at subpath (NOT root barrel) to
    // keep the @mostlyrightmd/core main bundle under its 25 KB size-limit
    // gate (TS-BUNDLE-01); same pattern as transforms / temporal /
    // formats / qc / validator.
    entry: { index: "src/discovery/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/discovery",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    // Phase 21 21-10 — `preprocessing` namespace surface (matches Python
    // `mostlyright.preprocessing`). Re-exports clipOutliers + PHYSICS_BOUNDS
    // from transforms/clip and iemCrosscheck (= crosscheckIemGhcnh) from
    // qc/crosscheck. Lives at subpath (NOT root barrel) per TS-BUNDLE-01.
    entry: { index: "src/preprocessing/index.ts" },
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outDir: "dist/preprocessing",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
];

// Build serialization. package.json "build" invokes `tsup` once per config via
// TSUP_ONLY=<index>. Each config's bundled-DTS runs in its own tsup worker
// thread (one Worker per array entry — see tsup build(): Promise.all over the
// config array). tsup's default array export fans all 12 out concurrently;
// every worker loads the full TS program, so on a 2-core CI runner the fan-out
// OOMs/contends and intermittently DROPS .d.ts outputs while the build still
// exits 0 with a partial dist/. Dependent packages then fail non-
// deterministically with TS7016 "Could not find a declaration file for module
// '@mostlyrightmd/core/...'". Running one DTS worker at a time makes it
// deterministic; config[0] (clean:true) runs first and clears dist/ before the
// clean:false subpath configs append. Keep the index list in package.json
// "build" in sync with allConfigs.length.
const only = process.env.TSUP_ONLY;
if (only !== undefined && only !== "") {
  const idx = Number(only);
  if (!Number.isInteger(idx) || idx < 0 || idx >= allConfigs.length) {
    throw new Error(`TSUP_ONLY=${only} is out of range [0, ${allConfigs.length - 1}]`);
  }
}

export default defineConfig(
  only !== undefined && only !== "" ? allConfigs[Number(only)] : allConfigs,
);
