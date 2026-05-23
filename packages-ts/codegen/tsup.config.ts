import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  // Codegen is build-only and never shipped to a browser, so we skip IIFE.
  format: ["esm", "cjs"],
  dts: true,
  sourcemap: true,
  clean: true,
  target: "es2022",
  outExtension({ format }) {
    if (format === "esm") return { js: ".mjs" };
    return { js: ".cjs" };
  },
});
