// Barrel for @mostlyrightmd/core/preprocessing (Phase 21 21-10).
//
// Surface-mirror of Python `mostlyright.preprocessing` (preprocessing.py):
//   - clipOutliers   ← clip_outliers (winsorize to physics bounds / sigma)
//   - PHYSICS_BOUNDS ← PHYSICS_BOUNDS (per-column [min, max] in canonical units)
//   - iemCrosscheck  ← iem_crosscheck (IEM vs GHCNh disagreement detection)
//
// These functions exist elsewhere in the TS codebase (clipOutliers +
// PHYSICS_BOUNDS in `@mostlyrightmd/core/transforms`, iemCrosscheck via
// crosscheckIemGhcnh in `@mostlyrightmd/core/qc`). This barrel re-exports
// them under the canonical `preprocessing` namespace so cross-language
// code reads the same way:
//
//   Python: from mostlyright.preprocessing import clip_outliers
//   TS:     import { clipOutliers } from "@mostlyrightmd/core/preprocessing"
//   TS:     import { preprocessing } from "mostlyright"
//           preprocessing.clipOutliers(...)
//
// Lives at the subpath (NOT root barrel) to keep the @mostlyrightmd/core
// main bundle under its 25 KB size-limit gate (TS-BUNDLE-01); same
// pattern as transforms / qc / temporal / formats / validator.

export {
  PHYSICS_BOUNDS,
  type ClipOutliersOptions,
  clipOutliers,
} from "../transforms/clip.js";

// `iemCrosscheck` is a sensible-defaults wrapper around the QC engine's
// crosscheckIemGhcnh — same surface contract as Python's iem_crosscheck.
export {
  crosscheckIemGhcnh as iemCrosscheck,
  type CrosscheckDisagreement,
  type CrosscheckOptions,
} from "../qc/crosscheck.js";
