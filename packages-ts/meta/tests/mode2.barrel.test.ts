// Barrel re-export test for TS-W4 Wave 1 Mode 2 surface.
//
// Verifies the meta package's root barrel (`packages-ts/meta/src/index.ts`)
// re-exports the Mode 2 surface so downstream consumers can do:
//
//   import { researchBySource, type Mode2Source } from "tradewinds";
//
// without a deep import. The bundle-size discipline (TS-BUNDLE-01) is
// enforced by `size-limit` post-build — this file only verifies the
// type + value re-exports are wired up correctly.

import { describe, expect, it } from "vitest";

import {
  MODE2_SOURCES,
  type Mode2Source,
  SOURCE_ALIASES,
  type SourceMismatchRole,
  assertSourceIdentity,
  isMode2Source,
  researchBySource,
} from "../src/index.js";

describe("meta barrel — TS-W4 Wave 1 Mode 2 surface", () => {
  it("re-exports researchBySource as a function", () => {
    expect(typeof researchBySource).toBe("function");
  });

  it("re-exports MODE2_SOURCES with exactly four canonical values", () => {
    expect([...MODE2_SOURCES]).toEqual(["iem.archive", "iem.live", "awc.live", "ghcnh.archive"]);
    expect(MODE2_SOURCES.length).toBe(4);
  });

  it("re-exports SOURCE_ALIASES with one entry per canonical source", () => {
    expect(SOURCE_ALIASES.size).toBe(4);
    expect(SOURCE_ALIASES.get("iem.archive")?.has("iem")).toBe(true);
    expect(SOURCE_ALIASES.get("awc.live")?.has("awc")).toBe(true);
    expect(SOURCE_ALIASES.get("ghcnh.archive")?.has("ghcnh")).toBe(true);
  });

  it("re-exports isMode2Source + assertSourceIdentity helpers", () => {
    expect(typeof isMode2Source).toBe("function");
    expect(typeof assertSourceIdentity).toBe("function");
    expect(isMode2Source("iem.archive")).toBe(true);
    expect(isMode2Source("iem")).toBe(false);
  });

  it("Mode2Source + SourceMismatchRole types are accessible from the barrel", () => {
    // Type-level check — assignments compile iff the type re-exports are wired.
    const canon: Mode2Source = "iem.archive";
    const role: SourceMismatchRole = "observations";
    expect(canon).toBe("iem.archive");
    expect(role).toBe("observations");
  });
});
