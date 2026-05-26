# mostlyright

Convenience meta-package for the [mostlyright](https://github.com/mostlyrightmd/mostlyright-sdk) TypeScript SDK. Re-exports the surfaces of `@mostlyrightmd/core`, `@mostlyrightmd/weather`, and `@mostlyrightmd/markets` so a single `import { research } from "mostlyright"` works.

If you only need one slice of the SDK, depend on the scoped packages directly. If you want everything in one import, this is the package.

## Install

```bash
pnpm add mostlyright
# or: npm install mostlyright
```

## Docs

See <https://mostlyright.md/docs/sdk/> for quickstart, concepts, and the full API reference.
