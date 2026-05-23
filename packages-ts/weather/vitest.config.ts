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
    alias: {
      "@tradewinds/core": resolve(__dirname, "../core/src/index.ts"),
    },
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
