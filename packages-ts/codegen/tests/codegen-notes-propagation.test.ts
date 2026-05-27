// Phase 21 Plan 21-08 — TSDoc emission from ColumnSpec.notes.
//
// Asserts that JSON Schema `description` fields (sourced from Python
// ColumnSpec.notes via scripts/export_schemas.py) propagate end-to-end into
// the generated TypeScript interfaces as TSDoc /** ... */ comments above
// each field.

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { type JSONSchema, compile } from "json-schema-to-typescript";
import ts from "typescript";
import { describe, expect, it } from "vitest";

/**
 * Phase 21 21-08 fix-iter-3 (codex HIGH): assert the codegen output is
 * SYNTACTICALLY VALID TypeScript, not just that the description text +
 * field declaration both appear. Without this, a raw `*\/` in the
 * description could close the TSDoc early, leave the field declaration
 * intact, and pass the substring assertions — while the generated file
 * doesn't compile.
 *
 * Uses `ts.transpileModule` (no type-checking, just parse) so the test
 * doesn't need to resolve project tsconfig + lib types.
 */
function assertCompiles(src: string, label: string): void {
  const result = ts.transpileModule(src, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      strict: false,
    },
    reportDiagnostics: true,
  });
  const diagnostics = result.diagnostics ?? [];
  if (diagnostics.length > 0) {
    const messages = diagnostics
      .map((d) => {
        const msg = ts.flattenDiagnosticMessageText(d.messageText, "\n");
        if (d.file && d.start !== undefined) {
          const { line, character } = d.file.getLineAndCharacterOfPosition(d.start);
          return `${label}:${line + 1}:${character + 1}: ${msg}`;
        }
        return `${label}: ${msg}`;
      })
      .join("\n");
    throw new Error(`Generated TS failed to parse:\n${messages}\n--- source ---\n${src}`);
  }
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const SCHEMAS_JSON_DIR = join(REPO_ROOT, "schemas", "json");
const GENERATED_DIR = join(REPO_ROOT, "packages-ts", "core", "src", "schemas", "generated");

// Match the codegen.ts call options exactly so the unit tests exercise the
// same emission pipeline as production codegen.
const COMPILE_OPTS = {
  bannerComment: "",
  style: { singleQuote: false, semi: true },
  additionalProperties: false,
  unreachableDefinitions: false,
} as const;

describe("codegen: description → TSDoc propagation (plan 21-08)", () => {
  it("emits a description as a TSDoc comment above the field (special chars escaped)", async () => {
    // Test that *closing* comment markers in descriptions don't break the
    // emitted TSDoc (would otherwise produce a syntax error).
    const schema: JSONSchema = {
      title: "TestSpecialCharsRow",
      type: "object",
      additionalProperties: false,
      properties: {
        column_a: {
          type: "string",
          description: "Description with closing comment marker: */ end",
        },
      },
      required: ["column_a"],
    };
    const out = await compile(schema, "TestSpecialCharsRow", COMPILE_OPTS);
    // The description must appear in TSDoc form somewhere in the output.
    expect(out).toMatch(/\/\*\*/);
    expect(out).toContain("Description with closing comment marker");
    expect(out).toMatch(/column_a:\s*string;/);
    // Phase 21 21-08 fix-iter-3 (codex HIGH): the emitted TS must actually
    // PARSE. A substring assertion alone would pass even if `*/` in the
    // description closed the TSDoc early, leaving a syntactically broken
    // file. Use ts.transpileModule to check the parser is happy.
    assertCompiles(out, "TestSpecialCharsRow");
  });

  it("does not emit empty /** */ stubs when description is missing", async () => {
    const schema: JSONSchema = {
      title: "TestNoDescRow",
      type: "object",
      additionalProperties: false,
      properties: {
        bare_field: { type: "string" },
      },
      required: ["bare_field"],
    };
    const out = await compile(schema, "TestNoDescRow", COMPILE_OPTS);
    // No empty TSDoc stub.
    expect(out).not.toMatch(/\/\*\*\s*\*\//);
    // The field still emits.
    expect(out).toMatch(/bare_field:\s*string;/);
  });

  it("preserves multi-line descriptions in TSDoc", async () => {
    const schema: JSONSchema = {
      title: "TestMultilineRow",
      type: "object",
      additionalProperties: false,
      properties: {
        many_lines: {
          type: "string",
          description: "First line.\nSecond line.\nThird line.",
        },
      },
      required: ["many_lines"],
    };
    const out = await compile(schema, "TestMultilineRow", COMPILE_OPTS);
    expect(out).toContain("First line.");
    expect(out).toContain("Second line.");
    expect(out).toContain("Third line.");
    expect(out).toMatch(/many_lines:\s*string;/);
  });

  it("is idempotent — compiling the same schema twice produces identical output", async () => {
    const schema: JSONSchema = {
      title: "TestIdempotencyRow",
      type: "object",
      additionalProperties: false,
      properties: {
        x: { type: "number", description: "Some described number." },
      },
      required: ["x"],
    };
    const a = await compile(schema, "TestIdempotencyRow", COMPILE_OPTS);
    const b = await compile(schema, "TestIdempotencyRow", COMPILE_OPTS);
    expect(a).toBe(b);
  });

  it("real observation schema: known descriptions appear as TSDoc above the matching fields", () => {
    // End-to-end check: the committed JSON schema lists descriptions, and the
    // committed generated .ts file carries them as TSDoc above each field.
    // If codegen ever drops the `description` reading (e.g. someone replaces
    // json-schema-to-typescript), this test fails immediately.
    const jsonSchemaRaw = readFileSync(
      join(SCHEMAS_JSON_DIR, "schema.observation.v1.json"),
      "utf8",
    );
    const jsonSchema = JSON.parse(jsonSchemaRaw) as {
      properties: Record<string, { description?: string }>;
    };
    const generatedRaw = readFileSync(join(GENERATED_DIR, "observation.v1.ts"), "utf8");

    // Pick three load-bearing columns with non-empty descriptions.
    const sampleColumns = ["station", "temp_c", "event_time"];
    for (const col of sampleColumns) {
      const spec = jsonSchema.properties[col];
      expect(spec, `column ${col} should exist in observation schema`).toBeDefined();
      const description = spec?.description;
      expect(
        description,
        `column ${col} should have a non-empty description in JSON Schema`,
      ).toBeTruthy();
      // The description string must appear in the generated file. We don't
      // assert exact ordering or formatting — just that the text is carried
      // through.
      expect(
        generatedRaw,
        `description for ${col} should appear in generated observation.v1.ts`,
      ).toContain(description ?? "");
    }

    // And the generated file uses TSDoc syntax (not // line comments).
    expect(generatedRaw).toMatch(/\/\*\*/);
  });
});
