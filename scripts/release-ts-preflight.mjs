#!/usr/bin/env node
// TS-W7 — release-ts.yml preflight.
//
// Normalizes the pushed tag and asserts the four package.json versions match
// the expected version before any `pnpm publish` runs. Also rewrites the
// inter-package peerDependencies range so the published packages declare
// the correct cross-pin (pnpm only rewrites `workspace:*`, NOT plain
// peerDependencies — codex iter-5 P1).
//
// Usage:  node scripts/release-ts-preflight.mjs <tag>
// where <tag> is e.g. `vts-0.1.0rc1` or `vts-0.1.0`.

import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const ROOT = resolve(import.meta.dirname ?? new URL(".", import.meta.url).pathname, "..");

const PACKAGES = [
  "packages-ts/core",
  "packages-ts/weather",
  "packages-ts/markets",
  "packages-ts/meta",
];

/**
 * `vts-0.1.0rc1` → `0.1.0-rc.1`
 * `vts-0.1.0rc12` → `0.1.0-rc.12`
 * `vts-0.1.0` → `0.1.0`
 * `vts-0.1.1` → `0.1.1`
 */
function tagToVersion(tag) {
  const m = /^vts-(\d+\.\d+\.\d+)(?:rc(\d+))?$/.exec(tag);
  if (m === null) {
    throw new Error(
      `tag ${JSON.stringify(tag)} does not match vts-X.Y.Z[rcN]; refusing to release.`,
    );
  }
  const base = m[1];
  const rc = m[2];
  return rc === undefined ? base : `${base}-rc.${rc}`;
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function writeJson(path, value) {
  await writeFile(path, JSON.stringify(value, null, 2) + "\n", "utf8");
}

async function main() {
  const tag = process.argv[2];
  if (typeof tag !== "string" || tag.length === 0) {
    console.error("usage: release-ts-preflight.mjs <tag>");
    process.exit(2);
  }
  const expected = tagToVersion(tag);
  console.log(`Tag ${tag} → npm version ${expected}`);

  // 1. Verify every package.json carries the expected version.
  const mismatches = [];
  for (const pkg of PACKAGES) {
    const path = resolve(ROOT, pkg, "package.json");
    const pj = await readJson(path);
    if (pj.version !== expected) {
      mismatches.push(`${pkg}: ${pj.version} (expected ${expected})`);
    }
  }
  if (mismatches.length > 0) {
    console.error("Version mismatch — refuse to publish:");
    for (const m of mismatches) console.error(`  - ${m}`);
    console.error(
      `Bump every package.json to ${expected} before tagging. See .changeset/README.md for the seed sequence.`,
    );
    process.exit(1);
  }

  // 2. Rewrite peerDependencies on @tradewinds/core to match the
  //    expected version. pnpm publish rewrites `workspace:*` but leaves
  //    plain peerDependencies untouched (codex iter-5 P1).
  for (const pkg of ["packages-ts/weather", "packages-ts/markets"]) {
    const path = resolve(ROOT, pkg, "package.json");
    const pj = await readJson(path);
    if (pj.peerDependencies?.["@tradewinds/core"] !== undefined) {
      const old = pj.peerDependencies["@tradewinds/core"];
      pj.peerDependencies["@tradewinds/core"] = `^${expected}`;
      console.log(
        `Rewrote ${pkg} peerDependencies['@tradewinds/core']: ${old} → ^${expected}`,
      );
      await writeJson(path, pj);
    }
  }

  console.log("Preflight green; safe to publish.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
