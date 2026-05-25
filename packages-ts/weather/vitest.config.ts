import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Alias workspace siblings to their source files so vitest can resolve
// @mostlyright/core without a pre-build step. Build still uses dist via
// the consumer's exports map. Mirrors the fix in packages-ts/meta/
// (TS-W0 iter-1 HIGH 5).
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
        find: "@mostlyright/core",
        replacement: resolve(__dirname, "../core/src/index.ts"),
      },
      // Phase 11 subpath alias — `@mostlyright/weather/live` is exported via
      // `package.json` `exports`, but vitest's alias resolver runs FIRST so
      // we need an explicit aliasing entry here too. Order matters — most
      // specific subpath BEFORE the bare-name alias.
      {
        find: "@mostlyright/weather/live",
        replacement: resolve(__dirname, "./src/live/index.ts"),
      },
      // Self-alias so backward-compat tests can import from @mostlyright/weather.
      {
        find: "@mostlyright/weather",
        replacement: resolve(__dirname, "./src/index.ts"),
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
