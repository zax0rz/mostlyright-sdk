import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    exclude: ["**/*.live.test.ts", "**/node_modules/**", "**/dist/**"],
    // Route browser-API tests (IndexedDB, navigator.locks) through jsdom;
    // everything else stays on Node default for speed.
    environmentMatchGlobs: [
      ["tests/internal/cache/indexeddb.test.ts", "jsdom"],
      ["tests/internal/cache/list-keys-idb.test.ts", "jsdom"],
      ["tests/internal/cache/default.test.ts", "jsdom"],
    ],
    setupFiles: ["./tests/setup-fake-indexeddb.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.ts"],
      exclude: [
        "**/generated/**",
        "**/*.d.ts",
        // Generated ajv-standalone compiled JS — emitted by codegen, not
        // hand-written; covered by the codegen smoke tests.
        "src/schemas/validators/**",
        // Data tables — pure constants, no branches to cover.
        "src/data/**",
      ],
      thresholds: {
        branches: 88,
        functions: 95,
        lines: 90,
        statements: 90,
      },
    },
  },
});
