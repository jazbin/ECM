# TBM Structural Field Comparison

> **Machine-generated** — do not hand-edit. Regenerate with:
> ```
> python3 tools/generate_tbm_structural_comparison.py
> ```

All values are extracted directly from the source TBM files. Prose and table
entries are always consistent because both come from the same extraction pass.

## Files compared

| Label | Path |
|-------|------|
| Source | `out/hp2170NCA-ECM.tbm` |
| HE18650 (known-good reference) | `BDS_files/_Projects/HE18650/he18650spiral1.tbm` |
| V3 (tabs-on, same-face) | `out/test/hp2170-test-v3-tabs-on-sameFace.tbm` |
| V4 (tabs-off, same-face) | `out/test/hp2170-test-v4-tabs-off-sameFace.tbm` |

## `m_dOffsetPosAvg` — Positive Offset (mm)

Two occurrences per file: one in the **Detailed Builder** (DB) section, one in the
**Simple Builder** (SB) section. Both are extracted independently.

| File | DB value | SB value |
|------|----------|----------|
| Source | 1e-06 | 0 |
| HE18650 | 0.5 | 0 |
| V3 | 1e-06 | 0 |
| V4 | 1e-06 | 0 |

**Notes:**

- Source DB = `1e-06`, Source SB = `0`. The DB value is the value set by About-Energy in the original ECM-mode TBM; it is close to zero but not identically zero.
- HE18650 (known-good Siemens stock reference) DB = `0.5`, SB = `0`.
- V3 inherits the source DB value unchanged (`1e-06`); its SB = `0`.
- V4 DB = `1e-06`, SB = `0`.
- V4 DB (`1e-06`) differs from HE18650 DB (`0.5`). To align with the known-good reference, regenerate V4 with DB = `0.5` via `tools/generate_tbm_test_variants.py` after adding the fix there.

## `m_dMandrelWidth` — Mandrel Width (mm)

| File | DB value | SB value |
|------|----------|----------|
| Source | 0 | 0 |
| HE18650 | 5 | 5 |
| V3 | 6 | 0 |
| V4 | 6 | 0 |

DB field name: `m_dMandrelWidth_mm`; SB field name: `m_dMandrelWidth` (no `_mm` suffix).

## `m_dElectrodeOverlapAtStart` — Electrode Overlap at Start (mm)

| File | DB value | SB value |
|------|----------|----------|
| Source | 0 | 8 |
| HE18650 | 30 | 30 |
| V3 | 8 | 8 |
| V4 | 8 | 8 |

Source DB = `0` was a placeholder left by About-Energy (TBM generated in 1D-only mode). BDS rejects zero with "Extrusion distance cannot be 0". V3 and V4 have this fixed to `8`.

## `m_bOnly1D` — 1D-only ECM flag (per SIMMOD, in document order)

| File | Values (all SIMODs that contain the field) |
|------|-------------------------------------------|
| Source | `[1, 1, 1, 1]` |
| HE18650 | `[1, 0, 0, 0]` |
| V3 | `[0, 0, 0, 0]` |
| V4 | `[0, 0, 0, 0]` |

**Notes:**

- Source has `[1, 1, 1, 1]`. All four SIMODs set to 1 because About-Energy generated this TBM in 1D-only ECM mode. BDS emits "Warning: m_bOnly1D option is not supported" for each occurrence and then fails to create the 3D geometry.
- HE18650 (known-good) has `[1, 0, 0, 0]`. The first SIMMOD retains `m_bOnly1D = 1` (from the stock template); the remaining three are 0. The file nonetheless builds successfully in BDS, indicating that only certain SIMMOD contexts cause BDS to reject the value.
- V3 has `[0, 0, 0, 0]` — all four zeroed by the variant generator to clear the BDS "not supported" error.
- V4 has `[0, 0, 0, 0]` — same as V3.

## Active RCRTable 3D — capacity fields

| File | `m_bSpecifyCapacity` | `m_dAhCell` (Ah) |
|------|---------------------|------------------|
| Source | 1 | 5.0 |
| HE18650 | 0 | 0 |
| V3 | 1 | 5.0 |
| V4 | 1 | 5.0 |

`m_bSpecifyCapacity = 1` with `m_dAhCell = 5.0 Ah` is the About-Energy NCA 2170 5 Ah specification. HE18650 has `m_bSpecifyCapacity = 0` because it relies on internal winding geometry to determine capacity.

