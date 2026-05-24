// Iter-1 H3 + iter-2 H6 + iter-8 H16 regression — verify the browser-facing
// cache subbundle does NOT statically OR dynamically import any Node-only
// modules.
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
});
