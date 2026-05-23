import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Alias workspace siblings to their source files so vitest can resolve
// @tradewinds/core without a pre-build step. Build still uses dist via
// the consumer's exports map. Mirrors the fix in packages-ts/meta/
// (TS-W0 iter-1 HIGH 5).
export default defineConfig({
  resolve: {
    alias: [
      // Order matters — most-specific (subpath) FIRST. Vite's alias resolver
      // walks the array in order and uses the first match, so a bare
      // "@tradewinds/core" entry above the subpaths would shadow them.
      {
        find: "@tradewinds/core/internal/bounds",
        replacement: resolve(__dirname, "../core/src/internal/bounds.ts"),
      },
      {
        find: "@tradewinds/core/internal/convert",
        replacement: resolve(__dirname, "../core/src/internal/convert.ts"),
      },
      {
        find: "@tradewinds/core",
        replacement: resolve(__dirname, "../core/src/index.ts"),
      },
    ],
  },
  test: {
    include: ["tests/**/*.test.ts"],
    exclude: ["**/*.live.test.ts", "**/node_modules/**", "**/dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.ts"],
      exclude: ["**/generated/**", "**/*.d.ts"],
    },
  },
});
