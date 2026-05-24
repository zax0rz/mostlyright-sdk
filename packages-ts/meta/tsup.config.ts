import { defineConfig } from "tsup";

// Two builds:
//   - Standard: external workspace deps (consumers resolve via node_modules).
//   - Bundled: single-file ESM with workspace deps inlined — for environments
//     that can't resolve bare specifiers (Chrome MV3 service workers, plain
//     <script type="module"> with no import-map, etc.). See TS-W1 iter-1 HIGH 5.
export default defineConfig([
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs", "iife"],
    globalName: "tradewinds",
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
    entry: { "index.bundle": "src/index.ts" },
    format: ["esm"],
    // Inline the three @tradewinds/* siblings so the output is loadable
    // from environments that don't support bare specifiers.
    noExternal: ["@tradewinds/core", "@tradewinds/weather", "@tradewinds/markets"],
    // Iter-9 H17: target Chrome MV3 service workers explicitly. tsup's
    // default `platform: "node"` makes esbuild resolve the "node" branch
    // of @tradewinds/core/internal/cache (via its conditional exports
    // map), pulling FsStore + proper-lockfile + node:fs/promises into a
    // sibling chunk that the bundle dynamic-imports. With
    // `platform: "browser"`, esbuild uses ["browser", "import",
    // "default"] conditions — routes the cache import to the browser
    // entry (which contains no FsStore reference, static OR dynamic) —
    // and the FsStore chunk is never emitted. Verified by the iter-9
    // H18 bundle-sanity assertion that scans the produced bundle.
    platform: "browser",
    outExtension: () => ({ js: ".mjs" }),
    sourcemap: true,
    clean: false,
    dts: false,
    target: "es2022",
  },
]);
