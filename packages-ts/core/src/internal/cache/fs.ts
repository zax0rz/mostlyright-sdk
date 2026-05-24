// FsStore — node:fs/promises + proper-lockfile CacheStore for Node runtimes.
//
// Path layout under the configured root:
//
//   <root>/<sanitized-key>.json
//
// Where `<root>` defaults to
// `$TRADEWINDS_CACHE_DIR ?? $HOME/.tradewinds/cache-ts` (per TS-CACHE-02 —
// distinct from Python's `.tradewinds/cache` so the JSON envelopes here
// can't shadow Python's parquet files).
//
// Atomic write: payload is written to `<path>.tmp` then renamed onto
// `<path>` (POSIX-atomic; Windows-safe via `fs.rename`).
//
// withLock uses proper-lockfile against a `<path>.lock` sidecar so two
// concurrent writers serialize per-key. The lock is taken with
// `realpath: false` so we can lock a path whose target may not yet
// exist.
//
// Divergence from Python: the Python cache is parquet + per-month station
// files keyed by (station, year, month); TS is JSON + per-key files keyed
// by the caller's opaque string. Station-aware key generation lives in
// `keys.ts` (plan 03).

import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

import * as properLockfile from "proper-lockfile";

import type { CacheEntry, CacheSetOptions, CacheStore } from "./types.js";

/**
 * Resolve the cache root on each call (not cached at module load) so tests
 * can `vi.stubEnv("TRADEWINDS_CACHE_DIR", ...)` between cases without a
 * module reload.
 *
 * Per TS-CACHE-02: defaults to `~/.tradewinds/cache-ts` — DISTINCT from
 * Python's `~/.tradewinds/cache` so JSON envelopes here can't shadow
 * Python's parquet files.
 */
export function defaultFsRoot(): string {
  const env = process.env.TRADEWINDS_CACHE_DIR;
  if (env !== undefined && env.length > 0) return env;
  return join(homedir(), ".tradewinds", "cache-ts");
}

export interface FsStoreOptions {
  /** Override root directory. Defaults to {@link defaultFsRoot}. */
  readonly root?: string;
}

/**
 * Node-side CacheStore. Each key maps to one JSON file under the root.
 */
export class FsStore implements CacheStore {
  readonly #root: string;
  // In-process per-key promise chain. proper-lockfile guarantees
  // cross-process exclusion but its retry-based contention resolution
  // is order-non-deterministic — two in-process callers racing on
  // `lock()` may acquire in either order. Layering an in-process chain
  // ensures strict FIFO for callers within the same Node process (and
  // serves as a cheap fast-path: only one of N in-process callers ever
  // actually contends with proper-lockfile).
  readonly #chain = new Map<string, Promise<unknown>>();

  constructor(opts: FsStoreOptions = {}) {
    this.#root = opts.root ?? defaultFsRoot();
  }

  /** Path resolver — `key` is sanitized so `:` / `/` don't escape the root. */
  #pathFor(key: string): string {
    const safe = key.replace(/[:/\\]/g, "__");
    return join(this.#root, `${safe}.json`);
  }

  async get<T = unknown>(key: string): Promise<T | null> {
    const p = this.#pathFor(key);
    let raw: string;
    try {
      raw = await readFile(p, "utf8");
    } catch (e: unknown) {
      const code = (e as { code?: string }).code;
      if (code === "ENOENT") return null;
      throw e;
    }
    let entry: CacheEntry<T>;
    try {
      entry = JSON.parse(raw) as CacheEntry<T>;
    } catch {
      // Corrupt cache entry — treat as miss; do NOT throw. Caller
      // re-fetches and overwrites.
      return null;
    }
    if (entry.expiresAt !== undefined && Date.now() >= entry.expiresAt) {
      // Lazy-evict: best-effort unlink, ignore failures.
      try {
        await rm(p, { force: true });
      } catch {
        // ignore
      }
      return null;
    }
    return entry.value as T;
  }

  async set<T = unknown>(key: string, value: T, opts?: CacheSetOptions): Promise<void> {
    const p = this.#pathFor(key);
    await mkdir(dirname(p), { recursive: true });
    const entry: CacheEntry<T> =
      opts?.ttlMs !== undefined ? { value, expiresAt: Date.now() + opts.ttlMs } : { value };
    const tmp = `${p}.tmp`;
    await writeFile(tmp, JSON.stringify(entry), "utf8");
    await rename(tmp, p);
  }

  async delete(key: string): Promise<void> {
    const p = this.#pathFor(key);
    try {
      await rm(p, { force: true });
    } catch (e: unknown) {
      const code = (e as { code?: string }).code;
      if (code === "ENOENT") return;
      throw e;
    }
  }

  async withLock<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const p = this.#pathFor(key);
    // Chain in-process callers FIFO. Cross-process exclusion is layered
    // on top via proper-lockfile inside `run()`.
    const prev = this.#chain.get(key) ?? Promise.resolve();
    const run = async (): Promise<T> => {
      await mkdir(dirname(p), { recursive: true });
      const release = await properLockfile.lock(p, {
        realpath: false,
        retries: { retries: 5, minTimeout: 20, maxTimeout: 200 },
      });
      try {
        return await fn();
      } finally {
        await release();
      }
    };
    const next = prev.then(run, run);
    // Absorber tail so the chain doesn't leak unhandled rejections.
    const absorbed = next.then(
      () => undefined,
      () => undefined,
    );
    this.#chain.set(key, absorbed);
    absorbed.finally(() => {
      if (this.#chain.get(key) === absorbed) this.#chain.delete(key);
    });
    return next;
  }
}
