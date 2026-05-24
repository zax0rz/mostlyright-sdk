# Changesets

This directory holds Changesets that describe pending releases of the
TypeScript packages. Read [the Changesets docs](https://github.com/changesets/changesets) for the full mental model.

## Lifecycle

1. **Author a changeset.** From the workspace root:
   ```bash
   pnpm changeset
   ```
   Pick which packages changed, the bump kind (major / minor / patch), and
   write a 1-line summary. Commits the resulting `.changeset/*.md` file.

2. **`changesets version` consumes changesets.** A repo maintainer runs:
   ```bash
   pnpm changeset version
   ```
   Updates the four packages' `package.json` versions in lockstep
   (`@tradewinds/core` + `@tradewinds/weather` + `@tradewinds/markets` +
   `tradewinds` meta are configured as a `fixed` set), regenerates
   `CHANGELOG.md` per package, and consumes the changeset markdown files.

3. **Tag + push.** Maintainer tags `vts-x.y.z[-rc.n]` and pushes; the
   [`release-ts.yml`](../.github/workflows/release-ts.yml) workflow then
   builds, tests, and publishes to npm via OIDC trusted publishing.

## v0.1.0 release plan

- `vts-0.1.0rc1` → npm `--tag next`, soak for ≥1 week against the in-repo
  `packages-ts/examples/chrome-extension-mvp/` sample.
- `vts-0.1.0` → npm `--tag latest`. P0 parity-ticket gate from
  `scripts/parity_status.py --milestone "TS v0.1.0"` must report zero
  open tickets.

## Config notes

- `commit: false` — the workflow generates one commit on `version`, then
  the maintainer reviews + lands it via a release PR. Mirrors Python's
  trusted-publishing discipline (workflow does the heavy lifting, human
  approves the tag).
- `fixed`: all four packages bump together. v0.1.x patch bumps for one
  package will move all four — keeps the meta package's inter-pin sound.
- `access: public` — the workflow publishes with `npm publish --access
  public` so first-publish of `@tradewinds/*` scoped packages succeeds.
