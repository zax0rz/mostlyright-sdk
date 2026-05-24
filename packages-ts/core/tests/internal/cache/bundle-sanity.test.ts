// Iter-1 H3 regression — verify the browser-facing cache subbundle does
// NOT statically import any Node-only modules. If `default.ts` ever
// re-introduces a top-level `import { FsStore } from "./fs.js"` (which
// transitively pulls `node:fs/promises`, `node:os`, `node:path`,
// `proper-lockfile` into the MV3 service-worker bundle), this test fails.
//
// The build must have run before this test — see `prebuild` in
// package.json. If `dist/` is absent (developer-only fresh clone), the
// test no-ops with a skip rather than masking a real regression.

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CACHE_BUNDLE = join(__dirname, "../../../dist/internal/cache/index.mjs");

const NODE_ONLY_PATTERNS = [
  "node:fs/promises",
  "node:fs ",
  "node:os",
  "node:path",
  "proper-lockfile",
];

describe("cache subbundle browser-safety (iter-1 H3 regression)", () => {
  it("dist/internal/cache/index.mjs does NOT statically import Node-only modules", () => {
    if (!existsSync(CACHE_BUNDLE)) {
      // Skip rather than fail in dev environments where the build hasn't run.
      console.warn(`[bundle-sanity] skipped: ${CACHE_BUNDLE} not built yet`);
      return;
    }
    const bundle = readFileSync(CACHE_BUNDLE, "utf8");
    for (const pattern of NODE_ONLY_PATTERNS) {
      // Allow `await import("...fs...")` dynamic chunks; reject top-level
      // `import {...} from "node:fs/promises"` style statements. A static
      // `import` statement always appears at the top of the file outside
      // any function — we look for the literal pattern surrounded by a
      // module-string context (quote chars).
      const inStaticImport = bundle.includes(`from "${pattern}"`);
      expect(
        inStaticImport,
        `cache subbundle must not statically import ${pattern}; H3 regression`,
      ).toBe(false);
    }
  });
});
