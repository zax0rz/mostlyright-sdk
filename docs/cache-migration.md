# Cache Migration: tradewinds → mostlyright

Phase 12 renamed the SDK from `tradewinds` to `mostlyright`. The on-disk cache
directory and the environment variable that overrides it follow the same rename.

## Old → New

| Old                            | New                              |
|--------------------------------|----------------------------------|
| `~/.tradewinds/cache/v1/`      | `~/.mostlyright/cache/v1/`       |
| `TRADEWINDS_CACHE_DIR` env var | `MOSTLYRIGHT_CACHE_DIR` env var  |

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

v0.2.x reads `TRADEWINDS_CACHE_DIR` as a fallback when `MOSTLYRIGHT_CACHE_DIR`
is unset, emitting a `DeprecationWarning`. v0.3 will remove the legacy branch.

To suppress the warning, switch to `MOSTLYRIGHT_CACHE_DIR` now.

## Resolution order (canonical → legacy → default)

1. `MOSTLYRIGHT_CACHE_DIR` env var (canonical).
2. `TRADEWINDS_CACHE_DIR` env var (legacy + emits `DeprecationWarning`;
   scheduled removal v0.3).
3. Default: `~/.mostlyright/cache/v1/`.

The canonical resolver is `mostlyright._internal._cache_dir.resolve_cache_dir`.
Existing call sites continue to read env vars locally to preserve the legacy
"env var = root, /v1 appended by callers" contract; new code should call
`resolve_cache_dir()` which returns the full cache directory (with `/v1`).
