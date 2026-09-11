# E004 Campaign Independent Review — 2026-09-11

Reviewed commit: `284baccb7149c68dfebea8e8779c1ce071db2925`

## Overall judgment

The C00–C17 campaign design is technically strong and the generated diagnostic TBMs appear suitable for runtime localization of E004. The axial-clearance additions C14–C17 materially improve the campaign because the failed project baseline has zero/negative package-to-layer axial margins while the Siemens validation reference has positive margins.

Do **not** send ZIP SHA-256 `5fc9776510e707f3e058ad4948b3768e3dd12bbbf06ef31d7c2060ac91bbd2f9` yet. Two reporting/interpretation defects should be corrected and the package regenerated. These defects are in campaign metadata/logic, not in the C14–C17 TBM deltas themselves.

## Finding 1 — CAMPAIGN_MATRIX axial metadata is wrong for C00 and C13

`make_row()` defaults to the project-baseline axial dimensions:

- package internal height = 65.11 mm
- separator width = 67.11 mm
- negative width = 65.11 mm
- positive width = 64.11 mm

The C00 and C13 `make_row()` calls do not override these defaults.

Therefore the generated CSV/MD currently report project-baseline axial values for C00 and C13 even though both contain Siemens Physical Cell Description geometry.

### Correct C00/C13 values

From Siemens `validationBattery.tbm`:

- package internal height = 60 mm
- separator width = 59 mm
- negative electrode width = 57 mm
- positive electrode width = 56 mm
- package − separator = +1 mm
- package − negative = +3 mm
- package − positive = +4 mm

C13 was independently checked at commit `284bacc`: its TBM really contains `Package m_dintHeight = 60`, confirming the TBM is correct and the matrix is wrong.

### Required fix

Parse C00/C13 axial values directly from the actual Siemens/control content rather than relying on `make_row()` defaults. Add a regression assertion that matrix values equal values parsed from each emitted TBM for all geometry columns.

## Finding 2 — C13 interpretation statement is too strong / partly reversed

Current matrix purpose text says, in effect:

- if C12 passes but C13 fails, E004 involves Physical Cell Description interaction;
- if C13 passes, E004 is confirmed localized to project Detailed Builder content.

The second statement is too strong because C13 changes **both** the Physical Cell Description and the Detailed Builder. A C13 pass by itself does not localize the cause to the project Builder.

### Correct paired interpretation

- `C12 PASS`: replacing only the project Detailed Builder with the Siemens Builder is sufficient to clear E004 under the project PCD. This strongly localizes E004 to project Detailed Builder content (or a project-Builder-specific derived construction), not to the project PCD alone.
- `C12 FAIL + C13 PASS`: changing the Siemens PCD in addition to the Siemens Builder is necessary; project PCD / PCD–Builder interaction is implicated.
- `C12 PASS + C13 PASS`: project Detailed Builder is the dominant localization result.
- `C12 PASS + C13 FAIL`: anomalous cross-interaction; Siemens PCD plus project model/SIMMOD context introduces a failure and must be treated separately, not simply as "PCD interaction".
- `C12 FAIL + C13 FAIL` while `C00 PASS`: the blocker is not eliminated by Siemens geometry transplants inside the project model context; investigate geometry/model coupling or non-transplanted sections.

Update README/matrix/result-interpretation text accordingly.

## Verified positive points

- C14 changes only `Package m_dintHeight: 65.11 -> 68.11` and yields intended +1/+3/+4 mm axial margins.
- C15 combines C14 with feed/tail 10/85.
- C16/C17 reduce all three positive-electrode width representations and all three negative-electrode width representations consistently, plus separator width, preserving the intended nested 2 mm / 1 mm differences.
- C16/C17 are correctly labelled diagnostic-only because changing electrode widths can affect active area / spatial electrical mapping.
- Baseline `Package m_bintVolCalc = 1`, so changing `Package m_dintHeight` while leaving stored internal-volume residue untouched is acceptable for this diagnostic campaign; STAR is instructed to calculate internal volume.
- E00 RCR-data-only import is correctly separated from 3D CAD-builder success. A PASS there would establish table ingestion only, not distributed electrical completeness.
- Selective-import tests are correctly deferred until Robert provides the exact `Import Battery Options` object list/screenshot.

## Release gate

After correcting Findings 1–2, rerun the deterministic generator, regenerate CSV/MD/README/ZIP, re-run validators/protected-field checks, and issue a new ZIP SHA-256. No C14–C17 TBM physics/geometry changes are requested by this review.
