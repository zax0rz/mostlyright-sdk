import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Per-worker FsStore root isolation lives in ./tests/setup-cache.ts —
// each vitest worker gets its own tmp dir (so cross-file tests can't
// share cached responses), AND beforeEach wipes the dir between tests
// in the same worker.

// Alias workspace siblings to their source files so vitest can resolve
// @mostlyright/core, @mostlyright/weather, @mostlyright/markets without a
// pre-build step. Build still uses dist via the consumers' exports map.
// See TS-W0 iter-1 HIGH 5.
export default defineConfig({
  resolve: {
    alias: [
      // Order matters — most-specific (subpath) FIRST. Vite's alias resolver
      // walks the array in order and uses the first match, so a bare
      // "@mostlyright/core" entry above the subpaths would shadow them.
      {
        find: "@mostlyright/core/internal/bounds",
        replacement: resolve(__dirname, "../core/src/internal/bounds.ts"),
      },
      {
        find: "@mostlyright/core/internal/convert",
        replacement: resolve(__dirname, "../core/src/internal/convert.ts"),
      },
      {
        find: "@mostlyright/core/internal/merge",
        replacement: resolve(__dirname, "../core/src/internal/merge/index.ts"),
      },
      {
        find: "@mostlyright/core/internal/pairs",
        replacement: resolve(__dirname, "../core/src/internal/pairs.ts"),
      },
      {
        find: "@mostlyright/core/internal/cache",
        replacement: resolve(__dirname, "../core/src/internal/cache/index.ts"),
      },
      {
        find: "@mostlyright/core/temporal",
        replacement: resolve(__dirname, "../core/src/temporal/index.ts"),
      },
      {
        find: "@mostlyright/core/formats",
        replacement: resolve(__dirname, "../core/src/formats/index.ts"),
      },
      {
        find: "@mostlyright/core/discovery",
        replacement: resolve(__dirname, "../core/src/discovery/index.ts"),
      },
      {
        find: "@mostlyright/core/qc",
        replacement: resolve(__dirname, "../core/src/qc/index.ts"),
      },
      {
        find: "@mostlyright/core",
        replacement: resolve(__dirname, "../core/src/index.ts"),
      },
      {
        find: "@mostlyright/weather",
        replacement: resolve(__dirname, "../weather/src/index.ts"),
      },
      {
        find: "@mostlyright/markets/polymarket",
        replacement: resolve(__dirname, "../markets/src/polymarket/index.ts"),
      },
      {
        find: "@mostlyright/markets",
        replacement: resolve(__dirname, "../markets/src/index.ts"),
      },
    ],
  },
  test: {
    include: ["tests/**/*.test.ts"],
    exclude: ["**/*.live.test.ts", "**/node_modules/**", "**/dist/**"],
    setupFiles: ["./tests/setup-cache.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.ts"],
      exclude: ["**/generated/**", "**/*.d.ts"],
    },
  },
});
