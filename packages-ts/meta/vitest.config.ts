import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Alias workspace siblings to their source files so vitest can resolve
// @tradewinds/core, @tradewinds/weather, @tradewinds/markets without a
// pre-build step. Build still uses dist via the consumers' exports map.
// See TS-W0 iter-1 HIGH 5.
export default defineConfig({
  resolve: {
    alias: {
      "@tradewinds/core": resolve(__dirname, "../core/src/index.ts"),
      "@tradewinds/weather": resolve(__dirname, "../weather/src/index.ts"),
      "@tradewinds/markets": resolve(__dirname, "../markets/src/index.ts"),
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
