// Iter-1 H3 + iter-2 H6 + iter-8 H16 + iter-9 H18 regression — verify the
// browser-facing cache subbundle does NOT statically OR dynamically import
// any Node-only modules.
//
// Iter-1 H3 fix made `defaultCacheStore` use a dynamic `import('./fs.js')`,
// but the barrel `index.ts` STILL re-exported FsStore/defaultFsRoot — so
// tsup hoisted them into a sibling chunk that the subbundle top-level-
// imports. The iter-1 bundle-sanity test only scanned `dist/internal/
// cache/index.mjs` and missed the chunk, false-passing.
//
// Iter-2 H6 fix: walked every chunk reachable from the subbundle (parse
// `import ... from "<rel-path>"` lines, resolve them recursively up to a
// depth bound) and grepped ALL of them for the Node-only patterns. That
// caught the static re-export chain.
//
// Iter-8 H16 fix (this test): the H6 regex only matched static
// `import/export ... from`. It silently missed `await import("./fs.js")`,
// which esbuild STILL follows when bundling for browser/MV3 — that's why
// `pnpm size` fails for the meta bundle even though this test was green.
// The walker now also matches `import(...)` (dynamic) so the reachability
// graph reflects what esbuild actually sees.
//
// Iter-8 H15 fix (paired): the architectural fix splits the cache entry
// into a Node entry (`index.ts` — keeps the dynamic FsStore import) and a
// browser entry (`index.browser.ts` — NO reference to FsStore, static OR
// dynamic). package.json conditional exports route browser/MV3 bundlers
// to the browser entry, eliminating the Node-only-deps edge by
// construction. This test asserts BOTH entries against their target's
// expected pattern set:
//   - Node entry: Node-only patterns ARE allowed (FsStore lives here).
//   - Browser entry: Node-only patterns MUST be absent (catches drift).
//
// Iter-9 H18 fix (this test): the iter-8 split was correct, but the
// conditional-exports map only takes effect when the bundler is configured
// to use browser conditions. The meta package's `index.bundle.mjs` build
// inlines workspace siblings via tsup's `noExternal` for MV3 service
// workers — but defaults to `platform: "node"`, so esbuild resolves the
// "node" branch of `@mostlyrightmd/core/internal/cache` and hoists FsStore +
// proper-lockfile + node:fs/promises into the bundle's sibling chunk
// (`fs-XXXX.mjs`). The H18 assertion scans the ACTUAL MV3-deployed
// artifact (`packages-ts/meta/dist/index.bundle.mjs`) — the H15/H16
// assertions only scan the in-package subbundle, which was browser-safe
// by construction but doesn't reflect what the chrome-extension-mvp
// example loads.
//
// The build must have run before this test — see `prebuild` in
// package.json. If `dist/` is absent (developer-only fresh clone), the
// test no-ops with a skip rather than masking a real regression.

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CACHE_BUNDLE_NODE = join(__dirname, "../../../dist/internal/cache/index.mjs");
const CACHE_BUNDLE_BROWSER = join(__dirname, "../../../dist/internal/cache/index.browser.mjs");
// Iter-9 H18: the MV3-deployed artifact lives in the meta package's
// `dist/`. The bundled build inlines workspace siblings (noExternal), so
// when tsup defaults to `platform: "node"` the cache entry resolves via
// its "node" conditional export — pulling FsStore + proper-lockfile +
// node:fs/promises into a sibling chunk next to `index.bundle.mjs`. This
// path lets the same `findViolations` walker scan that artifact too.
//
// Relative to this test file
// (`packages-ts/core/tests/internal/cache/bundle-sanity.test.ts`):
// go up 4 levels to `packages-ts/`, then into `meta/dist/`.
const META_BUNDLE_MV3 = join(__dirname, "../../../../meta/dist/index.bundle.mjs");
// Iter-10 H19: the IIFE bundle (`index.global.js`) is the artifact loaded
// via `<script>` tags in plain HTML pages. tsup's first defineConfig entry
// used to emit ESM + CJS + IIFE together with no `platform: "browser"`
// directive. ESM/CJS kept workspace deps external (consumers resolve via
// node_modules), but IIFE auto-inlines via `globalName` — and without
// browser conditions esbuild resolves the "node" branch of
// @mostlyrightmd/core/internal/cache, inlining FsStore + proper-lockfile +
// node:fs/promises into the global bundle. Any browser <script> consumer
// throws at evaluation. This assertion scans the actual emitted IIFE and
// guards against the regression returning.
const META_BUNDLE_IIFE = join(__dirname, "../../../../meta/dist/index.global.js");

const NODE_ONLY_PATTERNS = [
  // Bare Node built-ins — static imports.
  'from "node:fs/promises"',
  'from "node:fs"',
  'from "node:os"',
  'from "node:path"',
  'from "node:crypto"',
  'from "proper-lockfile"',
  'from "fs"',
  'from "path"',
  // Dynamic import variants — `await import("node:fs")` etc.
  'import("node:fs/promises")',
  'import("node:fs")',
  'import("node:os")',
  'import("node:path")',
  'import("node:crypto")',
  'import("proper-lockfile")',
];

// Match BOTH static `import/export ... from "<spec>"` AND dynamic
// `import("<spec>")` where the spec is a relative path (./ or ../).
// Excludes bare module specifiers like "node:fs" — those are caught by
// NODE_ONLY_PATTERNS scan, not the reachability walker.
//
// Static branch: `(?:import|export)[\s\S]*?from\s+["'](\.\.?\/[^"']+)["']`
// Dynamic branch: `import\s*\(\s*["'](\.\.?\/[^"']+)["']\s*\)`
//
// The dynamic branch is what iter-8 H16 added — esbuild follows
// `await import("./fs.js")` into the FsStore chunk, so the reachability
// walker must too.
const REACHABLE_IMPORT_RE =
  /(?:(?:import|export)[\s\S]*?from\s+["'](\.\.?\/[^"']+)["'])|(?:import\s*\(\s*["'](\.\.?\/[^"']+)["']\s*\))/g;

function collectReachableChunks(entryAbs: string, depthLimit = 16): string[] {
  const visited = new Set<string>([entryAbs]);
  const queue: Array<{ path: string; depth: number }> = [{ path: entryAbs, depth: 0 }];
  while (queue.length > 0) {
    const { path: cur, depth } = queue.shift() as { path: string; depth: number };
    if (depth >= depthLimit) continue;
    if (!existsSync(cur)) continue;
    const body = readFileSync(cur, "utf8");
    // matchAll keeps the regex stateless across iterations — biome rejects
    // `while ((m = re.exec(body)) !== null)` (assignment-in-expression).
    for (const match of body.matchAll(REACHABLE_IMPORT_RE)) {
      // Static-branch capture = group 1; dynamic-branch capture = group 2.
      const spec = match[1] ?? match[2];
      if (spec === undefined) continue;
      const resolved = resolve(dirname(cur), spec);
      if (visited.has(resolved)) continue;
      visited.add(resolved);
      queue.push({ path: resolved, depth: depth + 1 });
    }
  }
  return Array.from(visited);
}

function findViolations(
  reachable: ReadonlyArray<string>,
): Array<{ file: string; pattern: string }> {
  const violations: Array<{ file: string; pattern: string }> = [];
  for (const chunkPath of reachable) {
    if (!existsSync(chunkPath)) continue;
    const body = readFileSync(chunkPath, "utf8");
    for (const pattern of NODE_ONLY_PATTERNS) {
      if (body.includes(pattern)) {
        violations.push({ file: chunkPath, pattern });
      }
    }
  }
  return violations;
}

describe("cache subbundle browser-safety (iter-1 H3 + iter-2 H6 + iter-8 H15/H16 regression)", () => {
  it("the BROWSER entry (dist/internal/cache/index.browser.mjs) and every reachable chunk must be free of Node-only modules (static AND dynamic)", () => {
    if (!existsSync(CACHE_BUNDLE_BROWSER)) {
      // Skip rather than fail in dev environments where the build hasn't run.
      // The iter-8 H15 fix introduces this entry; until that build lands the
      // test surfaces the iter-8 reproduction via the Node-entry block below.
      console.warn(`[bundle-sanity] skipped: ${CACHE_BUNDLE_BROWSER} not built yet`);
      return;
    }
    const reachable = collectReachableChunks(CACHE_BUNDLE_BROWSER);
    expect(reachable).toContain(CACHE_BUNDLE_BROWSER);
    const violations = findViolations(reachable);
    if (violations.length > 0) {
      const detail = violations.map((v) => `  - ${v.pattern} in ${v.file}`).join("\n");
      throw new Error(
        `Browser-facing cache subbundle (index.browser.mjs + reachable chunks) must not import Node-only modules — static OR dynamic.\nFound ${violations.length} violation(s):\n${detail}\n\nFix: drop the offending reference from packages-ts/core/src/internal/cache/index.browser.ts. The browser entry must NOT mention FsStore via any path (static import, dynamic import, or re-export). FsStore lives behind the Node-only entry (index.ts) and the dedicated subpath export (./internal/cache/fs).`,
      );
    }
  });

  it("the NODE entry (dist/internal/cache/index.mjs) is allowed to reach Node-only modules via its dynamic FsStore import — sanity-check the walker DOES follow the dynamic import", () => {
    // This is the regression-detection assertion for H16: the walker MUST
    // now match `await import("./fs.js")` (and the generated sibling-chunk
    // form `await import("../fs-XXXX.mjs")`). If the dynamic branch of
    // REACHABLE_IMPORT_RE regresses, this assertion fails — proving the
    // walker would otherwise miss the FsStore chunk and false-pass the
    // browser-entry check above.
    if (!existsSync(CACHE_BUNDLE_NODE)) {
      console.warn(`[bundle-sanity] skipped: ${CACHE_BUNDLE_NODE} not built yet`);
      return;
    }
    const reachable = collectReachableChunks(CACHE_BUNDLE_NODE);
    // Build expectation: the Node entry's dynamic `import('./fs.js')` (or its
    // tsup-hoisted sibling `import('../fs-XXXX.mjs')`) means the FsStore
    // chunk MUST be in the reachability set. If it isn't, the regex
    // regressed and the walker is back to missing dynamic imports.
    const reachedFs = reachable.some((p) => /\/(fs|fs-[A-Z0-9]+)\.mjs$/.test(p) && existsSync(p));
    expect(reachedFs, "walker must follow `await import(...)` into the FsStore chunk").toBe(true);
  });

  it("the META IIFE bundle (packages-ts/meta/dist/index.global.js) must be free of Node-only modules — this is the <script>-deployed artifact", () => {
    // Iter-10 H19: the IIFE bundle is what plain HTML pages load via
    // `<script src="index.global.js">`. tsup's first defineConfig entry
    // historically emitted ESM + CJS + IIFE together. ESM/CJS keep
    // `@mostlyrightmd/*` external, so consumers resolve them via node_modules.
    // IIFE auto-inlines workspace deps for `<script>` consumption — but
    // without `platform: "browser"`, esbuild defaults to node conditions
    // and resolves the "node" branch of `@mostlyrightmd/core/internal/cache`,
    // hoisting FsStore + proper-lockfile + node:fs/promises straight into
    // `index.global.js`. Any browser that evaluates that script throws on
    // `__require("node:fs/promises")` / `__require("node:crypto")` /
    // FsStore initialization.
    //
    // The iter-10 H19 fix splits IIFE into its own tsup entry with
    // `platform: "browser"` (esbuild then picks the browser conditional
    // export and routes the cache import to the FsStore-free
    // `index.browser.ts`). This assertion scans the actual emitted IIFE
    // — unlike the H18 MV3 bundle check above, the IIFE doesn't emit
    // sibling chunks (single-file by design), so the walker scan would
    // collapse to a one-file string-grep regardless; we still go through
    // the walker for consistency and to catch any future regression that
    // produces multi-file IIFE output.
    if (!existsSync(META_BUNDLE_IIFE)) {
      console.warn(
        `[bundle-sanity] skipped meta IIFE bundle check: ${META_BUNDLE_IIFE} not built yet. Run \`pnpm --filter mostlyright run build\` to materialize it.`,
      );
      return;
    }
    const reachable = collectReachableChunks(META_BUNDLE_IIFE);
    expect(reachable).toContain(META_BUNDLE_IIFE);
    const violations = findViolations(reachable);
    if (violations.length > 0) {
      const detail = violations.map((v) => `  - ${v.pattern} in ${v.file}`).join("\n");
      throw new Error(
        `Meta IIFE bundle (packages-ts/meta/dist/index.global.js + any reachable chunks) must not import Node-only modules. This is the artifact <script>-tag consumers load.\nFound ${violations.length} violation(s):\n${detail}\n\nFix: ensure the IIFE entry in packages-ts/meta/tsup.config.ts has \`platform: "browser"\`. Without it, esbuild defaults to node conditions and resolves the "node" branch of @mostlyrightmd/core/internal/cache, inlining FsStore + proper-lockfile + node:fs/promises into the IIFE.`,
      );
    }
  });

  it("the META MV3 bundle (packages-ts/meta/dist/index.bundle.mjs) and every reachable chunk must be free of Node-only modules — this is the ACTUAL MV3-deployed artifact", () => {
    // Iter-9 H18: the H15/H16 assertions only scan the in-package cache
    // subbundle, which was browser-safe by construction (a 755-byte
    // re-export shim). They never scan the artifact that the
    // chrome-extension-mvp example loads:
    //   `packages-ts/meta/dist/index.bundle.mjs`.
    //
    // That bundle is built by tsup with `noExternal` for the three
    // @mostlyrightmd/* siblings. Without an explicit `platform: "browser"`
    // (or equivalent esbuild `conditions` override), esbuild defaults to
    // node conditions, resolves the `"node"` branch of the cache entry,
    // and hoists FsStore + proper-lockfile + node:fs/promises into a
    // sibling chunk (`fs-XXXX.mjs`). The walker's dynamic-import branch
    // (H16) already follows `await import("./fs-XXXX.mjs")` into that
    // sibling, so once H17 lands (browser platform on the bundle build)
    // this assertion passes by construction.
    //
    // If the meta bundle hasn't been built yet (developer-only fresh
    // clone, or running this file in isolation without
    // `pnpm --filter mostlyright run build`), skip rather than fail —
    // matches the H15/H16 skip pattern above.
    if (!existsSync(META_BUNDLE_MV3)) {
      console.warn(
        `[bundle-sanity] skipped meta MV3 bundle check: ${META_BUNDLE_MV3} not built yet. Run \`pnpm --filter mostlyright run build\` to materialize it.`,
      );
      return;
    }
    const reachable = collectReachableChunks(META_BUNDLE_MV3);
    expect(reachable).toContain(META_BUNDLE_MV3);
    const violations = findViolations(reachable);
    if (violations.length > 0) {
      const detail = violations.map((v) => `  - ${v.pattern} in ${v.file}`).join("\n");
      throw new Error(
        `Meta MV3 bundle (packages-ts/meta/dist/index.bundle.mjs + reachable chunks) must not import Node-only modules — static OR dynamic. This is the artifact MV3 service workers load (see packages-ts/examples/chrome-extension-mvp/service-worker.js).\nFound ${violations.length} violation(s):\n${detail}\n\nFix: ensure packages-ts/meta/tsup.config.ts sets \`platform: "browser"\` on the bundled (noExternal) build entry. Without it, tsup/esbuild defaults to node conditions and resolves the "node" branch of @mostlyrightmd/core/internal/cache, which pulls FsStore + proper-lockfile + node:fs/promises into the bundle.`,
      );
    }
  });
});
