# E004 client-v2 runtime campaign — 2026-09-14

## Purpose

Audited client package for Robert to run through STAR-CCM+ `CreateFromTbm`.

The hard workflow requirement is:

> one TBM = one complete reusable battery-cell definition, with no Part-module geometry modifications after import.

This package is still a **runtime import/geometry diagnostic campaign**, not a production-certified physics package.

---

## Package

Local package name:

`hp2170NCA-STAR-E004-root-surrogate-client-v2-20260914.zip`

SHA-256:

`6c1c7768ffcf0c4106e8f0761f52758f0ab7048526da07e691fc462f6864d231`

TBM count: **32**

- `D00` control
- `H01-H13`
- `T01-T09`
- `F01-F08`
- new audited discriminator `F09`

The previously generated H/T/F TBMs were preserved unchanged to keep the existing DOE interpretable.

---

## Why F09 was added

External audit identified stale `Package m_dextVolume` / `Package m_dintVolume` values as a confirmed static inconsistency when target 2170 dimensions are used.

`F09_FULL2170_WORKING_DERIVED_HEIGHTS_SYNC_VOLUMES.tbm` is identical to `F04_FULL2170_WORKING_DERIVED_HEIGHTS.tbm` except:

```text
Package m_dextVolume = 24.4605 cm^3
Package m_dintVolume = 21.7584 cm^3
```

These correspond to the target cylindrical dimensions:

```text
OD          = 21.09 mm
external H  = 70.02 mm
ID          = 20.6274 mm
internal H  = 65.11 mm
```

F09 SHA-256:

`3a344c8bd556fad2ba2a596c45da1a6e79fce926f9b837c5ead41191a1e1c963`

### Interpretation

- `F04 PASS / F09 PASS`: package-volume inconsistency is not an import blocker in this context.
- `F04 FAIL / F09 PASS`: synchronized package volumes become a serious geometry/import dependency candidate.
- `F04 PASS / F09 FAIL`: investigate whether explicit volume values are consumed unexpectedly or whether the volume formula/semantics differ from simple cylindrical volume.
- same result in both: F09 still resolves a production-data consistency defect even if it does not affect import.

---

## Client return format

Robert does **not** need to export STEP for all cases.

Included CSV:

`hp2170NCA_STAR_TBM_runtime_results_for_Robert_V2_20260914.csv`

Columns:

```text
test id
tbm file
group
test purpose
import result
error message
```

Requested client response:

- `import result = PASS` when `CreateFromTbm` succeeds;
- `import result = FAIL` otherwise;
- for the familiar `Electrode Root 1 : Extrusion distance can not be 0` failure, `error message = E004` is sufficient;
- paste the complete error text only if STAR reaches a different error.

No STEP export is requested in this round.

After the runtime matrix identifies the most production-relevant PASS case, request **one STEP only** for topology inspection.

---

## Current interpretation priorities

### Priority 1 — root/tab geometry relation

The H/T/F campaign tests the currently strongest E004 hypothesis:

`tab/root derived height ~ tab length - electrode width`

The reference/working files maintain positive values; failing R005 has negative values on both polarities.

### Priority 2 — target 2170 geometry compatibility

T/F cases progressively combine:

- target axial electrode/separator widths;
- target can/JR radial dimensions;
- package envelope;
- root/tab surplus;
- remaining Builder changes.

### Priority 3 — package-volume consistency

F09 isolates the newly audited PCD volume inconsistency.

---

## Production issues deliberately NOT folded into this DOE

The following audit findings are real, but are intentionally not mass-edited into the runtime campaign because doing so would confound E004 localization:

- stale physical electrode/separator winding lengths;
- stale component masses/weights;
- cap-equivalent material/thermal mapping;
- exact shell-property mapping;
- entropy activation (`m_bUseEntropyData`);
- active-area behavior;
- REPORT regeneration/synchronization.

Resolve these after the import/root blocker is localized.

See:

`tbm_validation/TBM_EXTERNAL_AUDIT_20260914.md`
