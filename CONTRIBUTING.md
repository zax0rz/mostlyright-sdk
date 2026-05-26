# Contributing to mostlyright

Thanks for considering a contribution. Bug reports, feature requests, and pull requests are all welcome.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](./CODE_OF_CONDUCT.md). By participating, you agree to abide by its terms. Report unacceptable behavior to <vu@mostlyright.md>.

## Quick start

```bash
git clone https://github.com/mostlyrightmd/mostlyright-sdk.git
cd mostlyright-sdk
uv sync                                                # installs workspace + Python dev deps
pnpm install --frozen-lockfile                          # installs TS workspace deps
uv run pre-commit install                              # pre-commit hook (fast checks)
uv run pre-commit install --hook-type pre-push        # pre-push hook (test suite)
uv run pytest -m "not live" -q                        # fast Python tests, no network
pnpm -r run test                                       # TS tests across all packages
```

Python 3.11+. Node 18+. macOS / Linux supported; Windows via WSL.

## Workflow

1. **Branch per change.** Format: `<type>/<short-description>`, e.g. `feat/edgar-10k-fetcher`, `fix/iem-asos-tz-offset`, `docs/snapshot-quickstart`.
2. **Write tests first.** This repo follows TDD: RED → GREEN → REFACTOR. New code lands with tests; minimum 80% line coverage on touched files.
3. **Pre-commit + pre-push hooks are mandatory.** No `--no-verify`. If a hook fails, fix the underlying issue. Pre-commit runs fast checks (ruff, format, YAML/TOML validation); pre-push runs the fast test suite.
4. **Open a PR against `main`.** Describe the change in 2-3 sentences. Link relevant issues. Include before/after for visible behavior changes.
5. **CI must be green.** The PR can't merge until the test matrix passes (Python 3.11/3.12/3.13 + TypeScript build + typecheck + lint).
6. **Two-reviewer loop for changes that touch data semantics.** Anything that affects observation parsing, merge logic, schema versioning, or release plumbing gets a second-opinion review from a maintainer. Cosmetic / docs / trivial changes don't need this.

## Repository structure

```
mostlyright-sdk/
├── packages/                      # Python packages (PyPI)
│   ├── core/                      # mostlyrightmd — the join + schemas + temporal-safety
│   ├── weather/                   # mostlyrightmd-weather — AWC, IEM, GHCNh, NWS CLI
│   └── markets/                   # mostlyrightmd-markets — Kalshi, Polymarket
├── packages-ts/                   # TypeScript packages (npm)
│   ├── core/                      # @mostlyrightmd/core
│   ├── weather/                   # @mostlyrightmd/weather
│   ├── markets/                   # @mostlyrightmd/markets
│   ├── meta/                      # mostlyright (unscoped meta)
│   └── codegen/                   # build-only; not published
├── schemas/                       # canonical JSON Schemas (Python emits; TS consumes via codegen)
├── docs/                          # reference docs (sphinx config + adapter notes + migration guides)
├── tests/                         # repo-root integration tests + parity fixtures
└── scripts/                       # build wrappers + release helpers
```

The `mostlyright` Python module namespace and the `@mostlyrightmd/*` npm scope have first-class peer semantics — schemas, station registries, and source-priority policies are byte-identical across runtimes (Python emits the canonical JSON; TypeScript regenerates types from it on every build).

## Reporting issues

Use [GitHub Issues](https://github.com/mostlyrightmd/mostlyright-sdk/issues) for:

- **Bugs.** Include the SDK version, Python/Node version, OS, and a minimal reproducer.
- **Feature requests.** Describe the use case — what are you trying to do? What does the current API force you to work around?
- **Documentation gaps.** Linking to a specific section that's wrong or unclear is the fastest way to fix it.

For **security vulnerabilities**, do NOT file a public issue. See [`SECURITY.md`](./SECURITY.md) for the private disclosure process.

## Adding a new data source

Adding a new public-data vertical (SEC EDGAR, FRED, options data, etc.) follows the same pattern as the existing weather + markets verticals:

1. **New package directory.** `packages/<vertical>/` (Python) + `packages-ts/<vertical>/` (TypeScript). Mirror the structure of `packages/markets/` for reference.
2. **Schemas first.** Define the canonical JSON Schema(s) under `schemas/json/schema.<vertical>.v1.json`. Add to the registration list in `packages/core/src/mostlyright/core/schemas/__init__.py`.
3. **Python implementation.** Adapter, fetcher, parser. Source identity stamped on every DataFrame. Tests cover the parser + the merge into the canonical schema.
4. **TS port.** Mirror the Python public surface. Verify byte-equivalence on the parity fixtures.
5. **Docs.** Quickstart MDX + concept doc on the landing site. Update the Packages table in the root `README.md`.
6. **Release.** Bump versions in lockstep; tag `v<X.Y.Z>` (Python) + `vts-<X.Y.Z>` (TypeScript).

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
