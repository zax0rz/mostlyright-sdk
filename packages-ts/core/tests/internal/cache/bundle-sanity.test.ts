// Iter-1 H3 + iter-2 H6 regression — verify the browser-facing cache
// subbundle does NOT statically import any Node-only modules.
//
// Iter-1 H3 fix made `defaultCacheStore` use a dynamic `import('./fs.js')`,
// but the barrel `index.ts` STILL re-exported FsStore/defaultFsRoot — so
// tsup hoisted them into a sibling chunk that the subbundle top-level-
// imports. The iter-1 bundle-sanity test only scanned `dist/internal/
// cache/index.mjs` and missed the chunk, false-passing.
//
// Iter-2 H6 fix (this test): walk every chunk reachable from the
// subbundle (parse `import ... from "<rel-path>"` lines, resolve them
// recursively up to a depth bound) and grep ALL of them for the Node-only
// patterns. The test FAILS until iter-2 H5 drops the FsStore re-export
// from the barrel (then the chunk no longer ships, and the subbundle's
// only static imports stay browser-safe).
//
// The build must have run before this test — see `prebuild` in
// package.json. If `dist/` is absent (developer-only fresh clone), the
// test no-ops with a skip rather than masking a real regression.

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CACHE_BUNDLE = join(__dirname, "../../../dist/internal/cache/index.mjs");

const NODE_ONLY_PATTERNS = [
  'from "node:fs/promises"',
  'from "node:fs"',
  'from "node:os"',
  'from "node:path"',
  'from "node:crypto"',
  'from "proper-lockfile"',
  'from "fs"',
  'from "path"',
];

// Match `import ... from "<spec>"` (or re-export `export ... from`) where
// the spec is a relative path (./ or ../). Excludes bare module specifiers
// like "node:fs" — those are caught by NODE_ONLY_PATTERNS scan.
const RELATIVE_IMPORT_RE = /(?:import|export)[\s\S]*?from\s+["'](\.\.?\/[^"']+)["']/g;

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
    for (const match of body.matchAll(RELATIVE_IMPORT_RE)) {
      const spec = match[1];
      if (spec === undefined) continue;
      const resolved = resolve(dirname(cur), spec);
      if (visited.has(resolved)) continue;
      visited.add(resolved);
      queue.push({ path: resolved, depth: depth + 1 });
    }
  }
  return Array.from(visited);
}

describe("cache subbundle browser-safety (iter-1 H3 + iter-2 H6 regression)", () => {
  it("no chunk reachable from dist/internal/cache/index.mjs statically imports Node-only modules", () => {
    if (!existsSync(CACHE_BUNDLE)) {
      // Skip rather than fail in dev environments where the build hasn't run.
      console.warn(`[bundle-sanity] skipped: ${CACHE_BUNDLE} not built yet`);
      return;
    }
    const reachable = collectReachableChunks(CACHE_BUNDLE);
    // The entry itself must be in the visited set.
    expect(reachable).toContain(CACHE_BUNDLE);
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
    if (violations.length > 0) {
      const detail = violations.map((v) => `  - ${v.pattern} in ${v.file}`).join("\n");
      throw new Error(
        `Browser-facing cache subbundle (and reachable chunks) must not statically import Node-only modules.\nFound ${violations.length} violation(s):\n${detail}\n\nFix: drop the offending re-export from packages-ts/core/src/internal/cache/index.ts. Node-only stores (FsStore) must live behind a dedicated subpath export (./internal/cache/fs) and a runtime feature-detect (defaultCacheStore uses dynamic import for this).`,
      );
    }
  });
});
