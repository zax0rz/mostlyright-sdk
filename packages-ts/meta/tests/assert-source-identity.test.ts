// Tests for `assertSourceIdentity` + `isMode2Source` + `MODE2_SOURCES`.
//
// Mirrors the Python `mostlyright.mode2.assert_source_identity` test
// surface (defense-in-depth source-identity check at the Mode 2
// dispatch layer). Snake_case `toDict()` keys are asserted explicitly
// — wire-format parity with Python: `schema_source`, `data_source`,
// `role`, `catalog_warning`. See `.planning/REVIEW-DISCIPLINE.md`
// `<review_discipline>` HIGH gate.

import { describe, expect, it } from "vitest";

import { SourceMismatchError } from "@mostlyrightmd/core";

import {
  MODE2_SOURCES,
  SOURCE_ALIASES,
  assertSourceIdentity,
  isMode2Source,
} from "../src/mode2.js";

interface FakeRow {
  source?: string | null | undefined;
  observed_at?: string;
}

describe("MODE2_SOURCES — Mode 2 canonical vocabulary", () => {
  it("contains exactly the four canonical dotted strings", () => {
    expect(MODE2_SOURCES.length).toBe(4);
    expect([...MODE2_SOURCES]).toEqual(["iem.archive", "iem.live", "awc.live", "ghcnh.archive"]);
  });
});

describe("isMode2Source — type guard for canonical vocabulary", () => {
  it("accepts canonical dotted forms", () => {
    expect(isMode2Source("iem.archive")).toBe(true);
    expect(isMode2Source("iem.live")).toBe(true);
    expect(isMode2Source("awc.live")).toBe(true);
    expect(isMode2Source("ghcnh.archive")).toBe(true);
  });

  it("rejects bare parser-emitted forms (TS narrows what Python widens)", () => {
    expect(isMode2Source("iem")).toBe(false);
    expect(isMode2Source("awc")).toBe(false);
    expect(isMode2Source("ghcnh")).toBe(false);
  });

  it("rejects empty + non-string inputs", () => {
    expect(isMode2Source("")).toBe(false);
    expect(isMode2Source("nws")).toBe(false);
    expect(isMode2Source(undefined)).toBe(false);
    expect(isMode2Source(null)).toBe(false);
    expect(isMode2Source(42)).toBe(false);
  });
});

describe("assertSourceIdentity — string-form `expected`", () => {
  it("empty rows → no throw", () => {
    expect(() => assertSourceIdentity([], "iem.archive")).not.toThrow();
  });

  it("rows without source field → no throw (matches Python mode2.py:181-182)", () => {
    const rows: FakeRow[] = [{ observed_at: "2024-06-01T12:00:00Z" }];
    expect(() => assertSourceIdentity(rows, "iem.archive")).not.toThrow();
  });

  it("rows with null/undefined source → no throw (treated as missing)", () => {
    const rows: FakeRow[] = [
      { source: null, observed_at: "2024-06-01T12:00:00Z" },
      { source: undefined, observed_at: "2024-06-02T12:00:00Z" },
    ];
    expect(() => assertSourceIdentity(rows, "iem.archive")).not.toThrow();
  });

  it("all rows match expected → no throw", () => {
    const rows: FakeRow[] = [
      { source: "iem.archive", observed_at: "2024-06-01T12:00:00Z" },
      { source: "iem.archive", observed_at: "2024-06-02T12:00:00Z" },
    ];
    expect(() => assertSourceIdentity(rows, "iem.archive")).not.toThrow();
  });

  it("single mismatched row → throws SourceMismatchError with role + schemaSource + dataSource", () => {
    const rows: FakeRow[] = [{ source: "awc", observed_at: "2024-06-01T12:00:00Z" }];
    let thrown: unknown = null;
    try {
      assertSourceIdentity(rows, "iem.archive");
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(SourceMismatchError);
    const err = thrown as SourceMismatchError;
    expect(err.role).toBe("observations");
    expect(err.schemaSource).toBe("iem.archive");
    expect(err.dataSource).toBe("awc");
    expect(err.catalogWarning).toBeNull();
  });

  it("mixed mismatched rows → dataSource is first sorted distinct + message lists all", () => {
    const rows: FakeRow[] = [
      { source: "awc", observed_at: "2024-06-01T12:00:00Z" },
      { source: "awc", observed_at: "2024-06-01T13:00:00Z" },
      { source: "ghcnh", observed_at: "2024-06-01T14:00:00Z" },
    ];
    let thrown: unknown = null;
    try {
      assertSourceIdentity(rows, "iem.archive");
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(SourceMismatchError);
    const err = thrown as SourceMismatchError;
    expect(err.dataSource).toBe("awc"); // first sorted distinct
    expect(err.message).toContain("'awc'");
    expect(err.message).toContain("'ghcnh'");
    expect(err.message).toContain("3 row(s)");
  });

  it("err.toDict() emits snake_case wire-format keys (Python parity)", () => {
    const rows: FakeRow[] = [{ source: "awc" }];
    let thrown: unknown = null;
    try {
      assertSourceIdentity(rows, "iem.archive");
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(SourceMismatchError);
    const dict = (thrown as SourceMismatchError).toDict();
    // Snake-case keys (Python parity) — explicit hasOwn for each.
    expect(Object.hasOwn(dict, "schema_source")).toBe(true);
    expect(Object.hasOwn(dict, "data_source")).toBe(true);
    expect(Object.hasOwn(dict, "role")).toBe(true);
    expect(Object.hasOwn(dict, "catalog_warning")).toBe(true);
    expect(dict.schema_source).toBe("iem.archive");
    expect(dict.data_source).toBe("awc");
    expect(dict.role).toBe("observations");
    expect(dict.catalog_warning).toBeNull();
    // CamelCase MUST NOT be present (would be a wire-format break).
    expect(Object.hasOwn(dict, "schemaSource")).toBe(false);
    expect(Object.hasOwn(dict, "dataSource")).toBe(false);
    expect(Object.hasOwn(dict, "catalogWarning")).toBe(false);
  });

  it("role override → err.role reflects the caller-supplied value", () => {
    const rows: FakeRow[] = [{ source: "awc" }];
    let thrown: unknown = null;
    try {
      assertSourceIdentity(rows, "iem.archive", "forecasts");
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(SourceMismatchError);
    expect((thrown as SourceMismatchError).role).toBe("forecasts");
  });
});

describe("assertSourceIdentity — alias-set `expected` (TS-W4 Mode 2 bridge)", () => {
  it("accepts bare parser tag matching the alias set (no throw)", () => {
    // Mode 2 caller asks for 'iem.archive'; parsers emit bare 'iem'.
    // SOURCE_ALIASES.get('iem.archive') accepts both.
    const accept = SOURCE_ALIASES.get("iem.archive");
    expect(accept).toBeDefined();
    const rows: FakeRow[] = [
      { source: "iem", observed_at: "2024-06-01T12:00:00Z" },
      { source: "iem.archive", observed_at: "2024-06-02T12:00:00Z" },
    ];
    // biome-ignore lint/style/noNonNullAssertion: assertion above
    expect(() => assertSourceIdentity(rows, accept!)).not.toThrow();
  });

  it("rejects rows whose source is NOT in the alias set", () => {
    // Mode 2 caller asks for 'iem.archive'; encounters 'awc'.
    const accept = SOURCE_ALIASES.get("iem.archive");
    const rows: FakeRow[] = [
      { source: "iem", observed_at: "2024-06-01T12:00:00Z" }, // OK
      { source: "awc", observed_at: "2024-06-01T13:00:00Z" }, // NOT OK
    ];
    let thrown: unknown = null;
    try {
      // biome-ignore lint/style/noNonNullAssertion: assertion above
      assertSourceIdentity(rows, accept!);
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(SourceMismatchError);
    const err = thrown as SourceMismatchError;
    expect(err.dataSource).toBe("awc");
    // schemaSource label is the alias-set joined ("iem|iem.archive").
    expect(err.schemaSource).toBe("iem|iem.archive");
  });
});
