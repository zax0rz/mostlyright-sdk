// FsStore — node:fs/promises + proper-lockfile CacheStore for Node runtimes.
//
// Path layout under the configured root:
//
//   <root>/<sanitized-key>.json
//
// Where `<root>` defaults to
// `$MOSTLYRIGHT_CACHE_DIR ?? $TRADEWINDS_CACHE_DIR (legacy + warn) ??
// $HOME/.mostlyright/cache-ts` (per TS-CACHE-02 — distinct from Python's
// `.mostlyright/cache` so the JSON envelopes here can't shadow Python's
// parquet files). Phase 12 W4 + review-iter2: mirrors the Python back-compat
// shim semantics — canonical → legacy + DeprecationWarning → default.
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

import { randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

import * as properLockfile from "proper-lockfile";

import type { CacheEntry, CacheSetOptions, CacheStore } from "./types.js";

/**
 * Resolve the cache root on each call (not cached at module load) so tests
 * can `vi.stubEnv("MOSTLYRIGHT_CACHE_DIR", ...)` between cases without a
 * module reload.
 *
 * Resolution order (Phase 12 W4 + review-iter2 — mirrors Python shim):
 * 1. `MOSTLYRIGHT_CACHE_DIR` env var (canonical, post-Phase-12).
 * 2. `TRADEWINDS_CACHE_DIR` env var (legacy; emits a one-time deprecation
 *    `console.warn`; scheduled for removal in vts-0.3).
 * 3. `~/.mostlyright/cache-ts` (per TS-CACHE-02 — DISTINCT from Python's
 *    `~/.mostlyright/cache` so JSON envelopes here can't shadow Python's
 *    parquet files).
 */
let _legacyCacheDirWarned = false;

export function defaultFsRoot(): string {
  const canonical = process.env.MOSTLYRIGHT_CACHE_DIR;
  if (canonical !== undefined && canonical.length > 0) return canonical;
  const legacy = process.env.TRADEWINDS_CACHE_DIR;
  if (legacy !== undefined && legacy.length > 0) {
    if (!_legacyCacheDirWarned) {
      console.warn(
        "TRADEWINDS_CACHE_DIR is deprecated; use MOSTLYRIGHT_CACHE_DIR. " +
          "Support will be removed in vts-0.3. " +
          "Run: mv ~/.tradewinds ~/.mostlyright",
      );
      _legacyCacheDirWarned = true;
    }
    return legacy;
  }
  return join(homedir(), ".mostlyright", "cache-ts");
}

/** Reset the one-time TRADEWINDS_CACHE_DIR deprecation latch — TEST USE ONLY. */
export function _resetLegacyCacheDirWarn(): void {
  _legacyCacheDirWarned = false;
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

  /**
   * Path resolver — `key` is sanitized via `encodeURIComponent` so that
   *
   *   1. `:` `/` `\` cannot escape the root (all percent-encoded), and
   *   2. the key → file mapping is INJECTIVE: distinct keys always map to
   *      distinct files.
   *
   * Iter-13 C16 fix: the previous implementation collapsed `:` / `/` / `\`
   * to the literal substring `"__"`, which is a lossy mapping — `"a:b"`,
   * `"a/b"`, and the literal `"a__b"` all hashed to `a__b.json`, so one
   * key's write would silently overwrite (and corrupt subsequent reads of)
   * another key. `encodeURIComponent` is bijective on string inputs and
   * filesystem-safe on every platform we ship (POSIX + Windows): the
   * characters it leaves unescaped (alphanumerics, `-._~!*'()`) are all
   * legal in NTFS, APFS, and ext4 filenames, and `%` is itself legal.
   *
   * BREAKING in v0.1.0: on-disk cache files written by any prior
   * pre-release of this package use the old `__`-replacement scheme and
   * are unreadable after upgrade. This is acceptable for a local-first
   * cache: entries are regenerated on demand from live data, and the
   * cache directory can be safely deleted by the user.
   */
  #pathFor(key: string): string {
    const safe = encodeURIComponent(key);
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
    // Codex iter-2 C6: use a UNIQUE temp filename per write. Two concurrent
    // `set("same-key", ...)` calls would otherwise race on the shared
    // `<path>.tmp`: writer A creates `<path>.tmp` and renames it to
    // `<path>`; writer B's subsequent rename then fails with ENOENT
    // because A's rename moved B's-in-progress temp away. With a unique
    // per-write suffix, each writer owns its own temp file; rename-into-
    // place stays atomic on POSIX (last-rename-wins semantics — any of
    // the N concurrent writers' value will be the final cache contents,
    // documented at the test that covers this).
    const tmp = `${p}.${randomUUID()}.tmp`;
    try {
      await writeFile(tmp, JSON.stringify(entry), "utf8");
      await rename(tmp, p);
    } catch (e) {
      // Best-effort cleanup if rename failed (e.g. permissions). Don't
      // let a stale unique-temp file leak.
      try {
        await rm(tmp, { force: true });
      } catch {
        // ignore
      }
      throw e;
    }
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

  /**
   * Enumerate keys whose stored files exist under the cache root and whose
   * decoded form starts with `prefix`.
   *
   * Returns an empty list if the root directory does not exist (cold cache).
   *
   * TS-W6 Wave 1: used by `availability()` to count observation months and
   * climate years for a station. The file→key mapping is the inverse of
   * `#pathFor` (encodeURIComponent → strip `.json` → decodeURIComponent).
   */
  async listKeys(prefix: string): Promise<ReadonlyArray<string>> {
    let entries: string[];
    try {
      entries = await readdir(this.#root);
    } catch (e: unknown) {
      const code = (e as { code?: string }).code;
      if (code === "ENOENT") return Object.freeze([]);
      throw e;
    }
    const out: string[] = [];
    for (const name of entries) {
      if (!name.endsWith(".json")) continue;
      // Ignore the proper-lockfile lock sidecars and our own in-flight
      // unique-temp files (`<key>.json.<uuid>.tmp`) — they end with `.tmp`
      // not `.json`, so the suffix filter above already excludes them.
      // The lock directories proper-lockfile creates end with `.json.lock`
      // (a directory entry), also excluded by the `.json` suffix check.
      const encoded = name.slice(0, -".json".length);
      let decoded: string;
      try {
        decoded = decodeURIComponent(encoded);
      } catch {
        // Defensive: skip files whose names don't decode (manual placements,
        // partial writes, etc).
        continue;
      }
      if (decoded.startsWith(prefix)) {
        out.push(decoded);
      }
    }
    return Object.freeze(out);
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
