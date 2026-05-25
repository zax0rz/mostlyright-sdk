import { defineConfig } from "tsup";

export default defineConfig({
  // Phase 11: emit the `live/` subpath as a separate entry so
  // `import { stream } from "@mostlyright/weather/live"` resolves via the
  // `exports` map (`./live` → `./dist/live/index.{mjs,cjs,d.ts}`).
  // Phase 17 PLAN-11: same for `forecasts/` subpath.
  entry: [
    "src/index.ts",
    "src/live/index.ts",
    "src/forecasts/index.ts",
  ],
  format: ["esm", "cjs", "iife"],
  globalName: "mostlyrightWeather",
  dts: true,
  sourcemap: true,
  clean: true,
  target: "es2022",
  outExtension({ format }) {
    if (format === "esm") return { js: ".mjs" };
    if (format === "cjs") return { js: ".cjs" };
    return { js: ".global.js" };
  },
});
