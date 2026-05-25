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
   (`@mostlyright/core` + `@mostlyright/weather` + `@mostlyright/markets` +
   `mostlyright` meta are configured as a `fixed` set), regenerates
   `CHANGELOG.md` per package, and consumes the changeset markdown files.

3. **Tag + push.** Maintainer tags `vts-x.y.z[-rc.n]` and pushes; the
   [`release-ts.yml`](../.github/workflows/release-ts.yml) workflow then
   builds, tests, and publishes to npm via OIDC trusted publishing.

## v0.1.0 release plan

The four packages currently sit at `0.0.0`. npm versions are immutable
once published, so `vts-0.1.0rc1` and `vts-0.1.0` MUST publish under
different package versions or the second publish will be rejected
(codex iter-4 P1).

The rc tag publishes `0.1.0-rc.1`; the final tag publishes `0.1.0`.

```bash
# Step 1 — seed 0.1.0-rc.1 across all four packages, then tag vts-0.1.0rc1:
for pkg in packages-ts/core packages-ts/weather packages-ts/markets packages-ts/meta; do
  pnpm --filter "./$pkg" exec npm version 0.1.0-rc.1 --no-git-tag-version
done
git add -A && git commit -m "chore(release): seed 0.1.0-rc.1"
git tag vts-0.1.0rc1 && git push origin vts-0.1.0rc1
# release-ts.yml publishes --tag next.

# Step 2 — after the ≥1-week soak, bump to 0.1.0:
for pkg in packages-ts/core packages-ts/weather packages-ts/markets packages-ts/meta; do
  pnpm --filter "./$pkg" exec npm version 0.1.0 --no-git-tag-version
done
git add -A && git commit -m "chore(release): promote 0.1.0"
git tag vts-0.1.0 && git push origin vts-0.1.0
# release-ts.yml publishes --tag latest (after P0 parity-ticket gate).
```

For ongoing v0.1.x releases, switch to the changesets flow (`pnpm
changeset` / `pnpm changeset version`); the seed step above only
applies to the first publish.

- `vts-0.1.0rc1` → npm `--tag next`, soak for ≥1 week against the in-repo
  `packages-ts/examples/chrome-extension-mvp/` sample.
- `vts-0.1.0` → npm `--tag latest`. P0 parity-ticket gate from
  `scripts/parity_status.py --milestone "TS v0.1.0"` must report zero
  open tickets (release-ts.yml runs this on non-rc tags).

## Config notes

- `commit: false` — the workflow generates one commit on `version`, then
  the maintainer reviews + lands it via a release PR. Mirrors Python's
  trusted-publishing discipline (workflow does the heavy lifting, human
  approves the tag).
- `fixed`: all four packages bump together. v0.1.x patch bumps for one
  package will move all four — keeps the meta package's inter-pin sound.
- `access: public` — the workflow publishes with `npm publish --access
  public` so first-publish of `@mostlyright/*` scoped packages succeeds.
