// TS-W3 Plan 05 Task 2 — validateRows tests.
//
// Asserts:
//   - Python-vocabulary `violations[].rule` strings appear verbatim
//   - source-identity invariant fires correctly
//   - SchemaValidationError.toDict() emits snake_case wire shape

import { describe, expect, it } from "vitest";

import { SchemaValidationError, SourceMismatchError } from "../src/exceptions/index.js";
import { validateRows } from "../src/validator.js";

const VALID_OBS_ROW = {
  event_time: "2025-01-15T12:00:00Z",
  observation_type: "METAR" as const,
  station: "KNYC",
  source: "iem.archive",
  retrieved_at: "2025-01-15T12:30:00Z",
};

describe("validateRows — happy path", () => {
  it("returns rowCount/source/retrievedAt on valid input", () => {
    const result = validateRows([VALID_OBS_ROW], "schema.observation.v1");
    expect(result.rowCount).toBe(1);
    expect(result.source).toBe("iem.archive");
    expect(result.retrievedAt).toBe("2025-01-15T12:30:00Z");
  });

  it("accepts opts.source + opts.retrievedAt over row fields", () => {
    const row = { ...VALID_OBS_ROW };
    (row as unknown as Record<string, unknown>).source = undefined;
    (row as unknown as Record<string, unknown>).retrieved_at = undefined;
    const result = validateRows([{ ...row, source: "iem.archive" }], "schema.observation.v1", {
      source: "iem.archive",
      retrievedAt: "2025-02-01T00:00:00Z",
    });
    expect(result.source).toBe("iem.archive");
    expect(result.retrievedAt).toBe("2025-02-01T00:00:00Z");
  });
});

describe("validateRows — Python vocabulary violations", () => {
  it("unknown_schema_id when schema isn't registered", () => {
    try {
      validateRows([], "schema.does-not-exist");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({ rule: "unknown_schema_id" });
    }
  });

  it("source_attr_required when opts.source + rows[0].source both missing", () => {
    try {
      validateRows([], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({ rule: "source_attr_required" });
    }
  });

  it("source_column_required when rows non-empty but column missing", () => {
    // Need to satisfy opts.source resolution first, then the per-row check
    // fires. Pass opts.source to skip the attr-required branch.
    const rows = [
      {
        event_time: "2025-01-15T12:00:00Z",
        observation_type: "METAR",
        station: "KNYC",
        retrieved_at: "x",
      },
    ];
    try {
      validateRows(rows, "schema.observation.v1", { source: "iem.archive" });
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({
        column: "source",
        rule: "source_column_required",
      });
    }
  });

  it("SourceMismatchError when per-row source != resolved source", () => {
    const rows = [{ ...VALID_OBS_ROW, source: "awc.live" }];
    expect(() =>
      validateRows(rows, "schema.observation.v1", {
        source: "iem.archive",
        allowSourceDrift: "test override",
      }),
    ).toThrow(SourceMismatchError);
  });

  it("retrieved_at_required when opts.retrievedAt + rows[0].retrieved_at both missing", () => {
    const row = { ...VALID_OBS_ROW };
    (row as unknown as Record<string, unknown>).retrieved_at = undefined;
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      expect(err.violations[0]).toMatchObject({ rule: "retrieved_at_required" });
    }
  });

  it("required_column_missing when ajv flags a missing required prop", () => {
    const row = { ...VALID_OBS_ROW };
    (row as unknown as Record<string, unknown>).observation_type = undefined;
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find((v) => v.rule === "required_column_missing");
      expect(violation).toBeDefined();
      expect(violation).toMatchObject({
        rule: "required_column_missing",
        column: "observation_type",
      });
    }
  });

  it("dtype_mismatch on a wrong type for a non-nullable field", () => {
    const row = { ...VALID_OBS_ROW, station: 12345 };
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find((v) => v.rule === "dtype_mismatch");
      expect(violation).toBeDefined();
    }
  });

  it("enum_value_violation when an enum field gets an out-of-set value", () => {
    const row = { ...VALID_OBS_ROW, observation_type: "BOGUS" };
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find((v) => v.rule === "enum_value_violation");
      expect(violation).toBeDefined();
      expect(violation).toMatchObject({
        rule: "enum_value_violation",
        column: "observation_type",
      });
    }
  });

  it("mixed_null_sentinels when a column mixes null and undefined", () => {
    const rows = [
      { ...VALID_OBS_ROW, temp_c: null },
      { ...VALID_OBS_ROW, temp_c: undefined },
    ];
    try {
      validateRows(rows, "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find((v) => v.rule === "mixed_null_sentinels");
      expect(violation).toBeDefined();
      expect(violation).toMatchObject({
        rule: "mixed_null_sentinels",
        column: "temp_c",
      });
    }
  });
});

describe("validateRows — allowSourceDrift guards", () => {
  it("allowSourceDrift='valid reason' bypasses source-identity check", () => {
    const rows = [{ ...VALID_OBS_ROW, source: "custom.source" }];
    // Source mismatch (custom.source != iem.archive registered) but
    // allowSourceDrift permits it. Per-row check still requires matching
    // resolved source which IS custom.source.
    const result = validateRows(rows, "schema.observation.v1", {
      source: "custom.source",
      allowSourceDrift: "test reason",
    });
    expect(result.source).toBe("custom.source");
  });

  it("allowSourceDrift='' throws RangeError (must be non-empty after trim)", () => {
    expect(() =>
      validateRows([VALID_OBS_ROW], "schema.observation.v1", {
        allowSourceDrift: "   ",
      }),
    ).toThrow(RangeError);
  });

  it("allowSourceDrift non-string throws TypeError", () => {
    expect(() =>
      validateRows([VALID_OBS_ROW], "schema.observation.v1", {
        // @ts-expect-error — runtime defensive check
        allowSourceDrift: true,
      }),
    ).toThrow(TypeError);
  });
});

describe("validateRows — canonical source map parity with Python (iter-1 C2)", () => {
  // Truth lives in `packages/core/src/tradewinds/core/schemas/*.py` —
  // each Schema subclass's `_registered_source: ClassVar[str]`. Any
  // drift here falsely fails Python-stamped frames in the TS validator
  // (or vice versa). These tests pin the literal canonical source for
  // every schema_id the codegen emits.
  const CANONICAL_SOURCE: Readonly<Record<string, string>> = {
    "schema.observation.v1": "iem.archive",
    "schema.settlement.cli.v1": "cli.archive",
    "schema.forecast.iem_mos.v1": "iem.archive",
    "schema.observation_ledger.v1": "iem.archive",
    "schema.observation_qc.v1": "iem.archive",
  };

  for (const [schemaId, expectedSource] of Object.entries(CANONICAL_SOURCE)) {
    it(`${schemaId} canonical source is ${expectedSource} (Python parity)`, () => {
      // Use an obviously-wrong source for this schema. The validator must
      // throw SourceMismatchError citing the canonical (registered) source —
      // confirming the map entry is what Python claims.
      try {
        validateRows([], schemaId, { source: "definitely.not.canonical" });
        throw new Error(`expected SourceMismatchError for ${schemaId}`);
      } catch (e) {
        // Empty rows means we never get past the source-identity check
        // because rows.length === 0 — but the per-row check is gated on
        // rows.length > 0. So the mismatch IS the first error to fire.
        expect(e).toBeInstanceOf(SourceMismatchError);
        const err = e as SourceMismatchError;
        expect(err.schemaSource).toBe(expectedSource);
        expect(err.dataSource).toBe("definitely.not.canonical");
      }
    });
  }
});

describe("validateRows — date / date-time format post-pass (iter-2 C5)", () => {
  // Codegen's ajv uses `strict: false` + no addFormats, so `format: "date"` /
  // `"date-time"` keywords compile out. The format post-pass in validateRows
  // closes that gap; without it, malformed date-time strings would pass
  // validation silently. See packages-ts/codegen/src/codegen.ts header
  // comment + validator.ts §6b.

  it("rejects malformed date-time string with dtype_mismatch", () => {
    const row = { ...VALID_OBS_ROW, event_time: "not-an-iso-string" };
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "event_time",
      );
      expect(violation).toBeDefined();
    }
  });

  it("rejects naive (no-tz) date-time string with dtype_mismatch", () => {
    // Date-time WITHOUT a tz suffix — TimePoint rejects this; the post-pass
    // must mirror that contract so JSON wire payloads can't smuggle naive
    // timestamps past validation.
    const row = { ...VALID_OBS_ROW, event_time: "2025-01-15T12:00:00" };
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "event_time",
      );
      expect(violation).toBeDefined();
    }
  });

  it("rejects date-only string for a date-time field with dtype_mismatch", () => {
    const row = { ...VALID_OBS_ROW, event_time: "2025-01-15" };
    try {
      validateRows([row], "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "event_time",
      );
      expect(violation).toBeDefined();
    }
  });

  it("rejects malformed date string with dtype_mismatch (date format)", () => {
    // schema.settlement.cli.v1 has `observation_date` with format: "date".
    const cliRow = {
      cli_data_quality: "clean",
      event_time: "2025-01-15T12:00:00Z",
      observation_date: "not-a-date",
      product_release_time: "2025-01-15T12:30:00Z",
      report_type: "final",
      settlement_finality: "final",
      station: "KNYC",
      station_tz: "America/New_York",
      source: "cli.archive",
      retrieved_at: "2025-01-15T13:00:00Z",
    };
    try {
      validateRows([cliRow], "schema.settlement.cli.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "observation_date",
      );
      expect(violation).toBeDefined();
    }
  });

  it("rejects date-time string passed where date format is expected", () => {
    // observation_date is `format: "date"` — a full ISO date-time must NOT
    // sneak through.
    const cliRow = {
      cli_data_quality: "clean",
      event_time: "2025-01-15T12:00:00Z",
      observation_date: "2025-01-15T00:00:00Z",
      product_release_time: "2025-01-15T12:30:00Z",
      report_type: "final",
      settlement_finality: "final",
      station: "KNYC",
      station_tz: "America/New_York",
      source: "cli.archive",
      retrieved_at: "2025-01-15T13:00:00Z",
    };
    try {
      validateRows([cliRow], "schema.settlement.cli.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "observation_date",
      );
      expect(violation).toBeDefined();
    }
  });

  it("rejects invalid calendar date (e.g. 2025-02-30) with dtype_mismatch", () => {
    const cliRow = {
      cli_data_quality: "clean",
      event_time: "2025-01-15T12:00:00Z",
      observation_date: "2025-02-30",
      product_release_time: "2025-01-15T12:30:00Z",
      report_type: "final",
      settlement_finality: "final",
      station: "KNYC",
      station_tz: "America/New_York",
      source: "cli.archive",
      retrieved_at: "2025-01-15T13:00:00Z",
    };
    try {
      validateRows([cliRow], "schema.settlement.cli.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      expect(e).toBeInstanceOf(SchemaValidationError);
      const err = e as SchemaValidationError;
      const violation = err.violations.find(
        (v) => v.rule === "dtype_mismatch" && v.column === "observation_date",
      );
      expect(violation).toBeDefined();
    }
  });

  it("accepts valid date-time string with Z suffix", () => {
    const row = { ...VALID_OBS_ROW, event_time: "2025-01-15T12:00:00Z" };
    const result = validateRows([row], "schema.observation.v1");
    expect(result.rowCount).toBe(1);
  });

  it("accepts valid date-time string with +HH:MM offset", () => {
    const row = { ...VALID_OBS_ROW, event_time: "2025-01-15T12:00:00+02:00" };
    const result = validateRows([row], "schema.observation.v1");
    expect(result.rowCount).toBe(1);
  });

  it("accepts valid date and date-time strings together", () => {
    const cliRow = {
      cli_data_quality: "clean",
      event_time: "2025-01-15T12:00:00Z",
      observation_date: "2025-01-15",
      product_release_time: "2025-01-15T12:30:00Z",
      report_type: "final",
      settlement_finality: "final",
      station: "KNYC",
      station_tz: "America/New_York",
      source: "cli.archive",
      retrieved_at: "2025-01-15T13:00:00Z",
    };
    const result = validateRows([cliRow], "schema.settlement.cli.v1");
    expect(result.rowCount).toBe(1);
  });
});

describe("validateRows — error wire shape (snake_case parity)", () => {
  it("SchemaValidationError.toDict() emits snake_case schema_id / violations / quarantine_count / sample_violations", () => {
    try {
      validateRows([], "schema.does-not-exist");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      const err = e as SchemaValidationError;
      const dict = err.toDict();
      expect(Object.hasOwn(dict, "schema_id")).toBe(true);
      expect(Object.hasOwn(dict, "violations")).toBe(true);
      expect(Object.hasOwn(dict, "quarantine_count")).toBe(true);
      expect(Object.hasOwn(dict, "sample_violations")).toBe(true);
      // camelCase MUST NOT appear
      expect(Object.hasOwn(dict, "schemaId")).toBe(false);
    }
  });

  it("sampleViolations capped at 10 even when many rows fail", () => {
    const rows: Array<Record<string, unknown>> = [];
    for (let i = 0; i < 15; i++) {
      // Each row has wrong type for `station` (number where string expected).
      rows.push({ ...VALID_OBS_ROW, station: i });
    }
    try {
      validateRows(rows, "schema.observation.v1");
      throw new Error("expected SchemaValidationError");
    } catch (e) {
      const err = e as SchemaValidationError;
      expect(err.sampleViolations.length).toBeLessThanOrEqual(10);
    }
  });
});
