// TS-W3 Plan 05 Task 1 — codegen validator smoke tests.
//
// Asserts the codegen-emitted `getValidator` is the expected shape AND that
// the compiled .js files have no runtime ajv references (MV3-CSP-safe).

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const VALIDATORS_DIR = join(REPO_ROOT, "packages-ts", "core", "src", "schemas", "validators");

describe("codegen-emitted validators (TS-W3 Plan 05)", () => {
  it("getValidator resolves the canonical observation schema id", async () => {
    // Dynamic import — the generated module lives outside this package, so
    // resolve from REPO_ROOT and use the .ts path under tsx.
    const mod = (await import(`${VALIDATORS_DIR}/index.ts`)) as {
      getValidator: (id: string) => unknown;
      listValidators: () => readonly string[];
    };
    expect(typeof mod.getValidator).toBe("function");
    expect(mod.getValidator("schema.observation.v1")).toBeTypeOf("function");
    expect(mod.getValidator("schema.settlement.cli.v1")).toBeTypeOf("function");
    expect(mod.getValidator("unknown.schema")).toBeNull();
  });

  it("listValidators returns all registered schema ids", async () => {
    const mod = (await import(`${VALIDATORS_DIR}/index.ts`)) as {
      listValidators: () => readonly string[];
    };
    const ids = mod.listValidators();
    expect(ids.length).toBeGreaterThanOrEqual(3);
    expect(ids).toContain("schema.observation.v1");
    expect(ids).toContain("schema.settlement.cli.v1");
  });

  it("compiled .js validator has NO runtime ajv references", () => {
    const path = join(VALIDATORS_DIR, "schema_observation_v1.js");
    const contents = readFileSync(path, "utf8");
    // Allow `// ajv` in comments but not `require('ajv')` / `import ajv`.
    expect(contents).not.toMatch(/require\(['"]ajv['"]\)/);
    expect(contents).not.toMatch(/from ['"]ajv['"]/);
    expect(contents).not.toMatch(/import \* as ajv/);
  });
});
