import { defineConfig } from "tsup";

// Three builds:
//   - Standard ESM/CJS: external workspace deps (consumers resolve via node_modules).
//   - IIFE (index.global.js): inlines workspace deps for <script> consumption;
//     MUST target browser so esbuild picks the browser conditional-export of
//     @mostlyrightmd/core/internal/cache (else FsStore + proper-lockfile +
//     node:fs/promises get hoisted in via the "node" condition).
//   - Bundled (index.bundle.mjs): single-file ESM with workspace deps inlined
//     for Chrome MV3 service workers / plain <script type="module"> with no
//     import-map. See TS-W1 iter-1 HIGH 5.
//
// Iter-10 H19: the IIFE format used to share an entry with ESM/CJS, but
// IIFE auto-inlines workspace deps while ESM/CJS keep them external.
// Without an explicit `platform: "browser"` directive, esbuild defaults to
// node conditions for the IIFE inline-resolution and pulls FsStore + Node
// builtins into `index.global.js`, breaking any browser <script> consumer.
// Splitting IIFE into its own entry with `platform: "browser"` isolates the
// browser-condition resolution from the ESM/CJS Node-consumer path.
export default defineConfig([
  {
    entry: ["src/index.ts"],
    format: ["esm", "cjs"],
    dts: true,
    sourcemap: true,
    clean: true,
    target: "es2022",
    outExtension({ format }) {
      if (format === "esm") return { js: ".mjs" };
      return { js: ".cjs" };
    },
  },
  {
    entry: ["src/index.ts"],
    format: ["iife"],
    globalName: "mostlyright",
    // IIFE auto-inlines workspace deps for <script> consumption. Without
    // `platform: "browser"`, esbuild defaults to node conditions and
    // resolves the "node" branch of @mostlyrightmd/core/internal/cache,
    // hoisting FsStore + proper-lockfile + node:fs/promises into the
    // bundle. Browser platform routes the cache import to the browser
    // entry (no FsStore reference, static OR dynamic). Verified by the
    // iter-10 H19 bundle-sanity assertion that scans index.global.js.
    platform: "browser",
    dts: false,
    sourcemap: true,
    clean: false,
    target: "es2022",
    outExtension: () => ({ js: ".global.js" }),
  },
  {
    entry: { "index.bundle": "src/index.ts" },
    format: ["esm"],
    // Inline the three @mostlyrightmd/* siblings so the output is loadable
    // from environments that don't support bare specifiers.
    noExternal: ["@mostlyrightmd/core", "@mostlyrightmd/weather", "@mostlyrightmd/markets"],
    // Iter-9 H17: target Chrome MV3 service workers explicitly. tsup's
    // default `platform: "node"` makes esbuild resolve the "node" branch
    // of @mostlyrightmd/core/internal/cache (via its conditional exports
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
