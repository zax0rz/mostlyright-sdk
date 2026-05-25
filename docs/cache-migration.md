# Cache Migration: tradewinds → mostlyright

Phase 12 renamed the SDK from `tradewinds` to `mostlyright`. The on-disk cache
directory and the environment variable that overrides it follow the same rename
in **both the Python and the TypeScript SDKs** — the env var name is shared
across SDKs even though each SDK keeps its own on-disk subdirectory.

## Old → New

### Python SDK (`mostlyright` / `mostlyright-weather` / `mostlyright-markets`)

| Old                            | New                              |
|--------------------------------|----------------------------------|
| `~/.tradewinds/cache/v1/`      | `~/.mostlyright/cache/v1/`       |
| `TRADEWINDS_CACHE_DIR` env var | `MOSTLYRIGHT_CACHE_DIR` env var  |

### TypeScript SDK (`@mostlyrightmd/core` FsStore)

| Old                            | New                              |
|--------------------------------|----------------------------------|
| `~/.tradewinds/cache-ts/`      | `~/.mostlyright/cache-ts/`       |
| `TRADEWINDS_CACHE_DIR` env var | `MOSTLYRIGHT_CACHE_DIR` env var  |

TS uses a distinct `-ts` suffix on the cache subdirectory (per TS-CACHE-02) so
JSON envelopes from the TS FsStore can't shadow parquet files from the Python
cache. A single `mv ~/.tradewinds ~/.mostlyright` migrates both — the
sibling `cache/` and `cache-ts/` directories move together.

## How to migrate (default path)

Parquet schema is unchanged. A simple `mv` works:

```bash
mv ~/.tradewinds ~/.mostlyright
```

That's it — byte-equivalent, no re-fetch needed.

## How to migrate (custom env-var path)

If you set `TRADEWINDS_CACHE_DIR=/data/cache` in your shell:

```bash
# Update your shell rc file:
export MOSTLYRIGHT_CACHE_DIR=/data/cache    # canonical env var, same root semantic
unset TRADEWINDS_CACHE_DIR                  # silence the DeprecationWarning
```

The semantic is preserved: `MOSTLYRIGHT_CACHE_DIR` points at the cache **root**
(without `/v1`); the SDK appends `/v1/observations/...` etc. itself.

## Back-compat (one-release deprecation window)

Both SDKs read `TRADEWINDS_CACHE_DIR` as a fallback when `MOSTLYRIGHT_CACHE_DIR`
is unset and emit a deprecation notice. Removal is scheduled in the next
minor:

| SDK | Notice mechanism | Scheduled removal |
|-----|------------------|-------------------|
| Python | `DeprecationWarning` (raised once per resolver call) | `v0.3` |
| TypeScript | `console.warn` (latched: emitted once per process) | `vts-0.3` |

To suppress the warning, switch to `MOSTLYRIGHT_CACHE_DIR` now.

## Resolution order (canonical → legacy → default)

Both SDKs share the same resolution order:

1. `MOSTLYRIGHT_CACHE_DIR` env var (canonical).
2. `TRADEWINDS_CACHE_DIR` env var (legacy + emits deprecation notice;
   scheduled removal next minor — `v0.3` / `vts-0.3`).
3. Default:
   - Python: `~/.mostlyright/cache/v1/` (`v1` is the cache schema version).
   - TypeScript: `~/.mostlyright/cache-ts/` (distinct subdirectory; see
     TS-CACHE-02 — TS JSON envelopes never share a directory with Python
     parquet files).

### Python resolver

The canonical resolver is `mostlyright._internal._cache_dir.resolve_cache_dir`
which returns the full cache directory (with `/v1` default). The 3 existing
`_cache_root()` call sites (discovery.py, weather/cache.py,
markets/_trades_cache.py) use the companion
`resolve_cache_root_without_v1()` helper to preserve the legacy "env var =
root, callers append `/v1`" contract. Both helpers share a single
`_resolve_env_value()` source of truth, so the canonical → legacy + warn →
default resolution order can only change in one place.

### TypeScript resolver

The canonical resolver is `defaultFsRoot()` in
`@mostlyrightmd/core/internal/cache/fs`. It returns the full cache directory
directly (`~/.mostlyright/cache-ts/` default; no `/v1` segment because TS
uses per-key JSON files rather than per-month parquet). New `FsStore`
instances accept an explicit `root` option for callers that want to bypass
env-var resolution entirely.
