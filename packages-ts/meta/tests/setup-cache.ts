// Per-worker cache isolation. Each vitest worker creates its own unique
// FsStore root so tests across files don't share cached responses. Within
// a worker, `beforeEach` wipes the dir so tests within a file don't pollute
// each other either.

import { mkdtempSync } from "node:fs";
import { rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { beforeEach } from "vitest";

// Per-worker tmp dir — each setup-cache.ts module load creates a fresh one.
// process.env is per-process, so this isolates workers from each other AND
// from the user's $HOME/.mostlyright/cache-ts.
const workerRoot = mkdtempSync(join(tmpdir(), `tw-meta-test-w${process.pid}-`));
process.env.TRADEWINDS_CACHE_DIR = workerRoot;

beforeEach(async () => {
  // Wipe the worker root before each test — kills any cache state written
  // by the previous test in this worker.
  await rm(workerRoot, { recursive: true, force: true });
});
