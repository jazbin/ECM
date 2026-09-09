# TBM Structural Field Comparison

> **Machine-generated** — do not hand-edit. Regenerate with:
> ```
> python3 tools/generate_tbm_structural_comparison.py
> ```

All values are extracted directly from the TBM files using `tools/tbm_field_extractor.py`.
Prose and table entries are always consistent because both come from the same extraction pass.

**Naming convention:**
- `package_rev3 / variant_N` — the geometry-test package (sent 2026-09-09, commit e3c3b14)
- `package_rev4_candidate / variant_N` — the package_rev4_candidate review candidate (commit 2ea5b45, NOT yet sent to Robert)

Use `package_rev3`, `package_rev4_candidate`, and `variant_N` explicitly; package revision and variant identifiers must not be collapsed into shorthand.

## Files compared

| Label | Path |
|-------|------|
| source | `tbm_validation/source/hp2170NCA-ECM.tbm` |
| HE18650 (known-good reference) | `tbm_validation/reference/HE18650/he18650spiral1.tbm` |
| package_rev3 / variant_1 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm` |
| package_rev3 / variant_2 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v2-tabs-off-standard.tbm` |
| package_rev3 / variant_3 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v3-tabs-on-sameFace.tbm` |
| package_rev3 / variant_4 | `tbm_validation/variants/v3_package_20260909/hp2170-test-v4-tabs-off-sameFace.tbm` |
| package_rev4_candidate / variant_1 | `out/v4_candidate/hp2170-v4c-v1-tabs-on-standard.tbm` |
| package_rev4_candidate / variant_2 | `out/v4_candidate/hp2170-v4c-v2-tabs-off-standard.tbm` |
| package_rev4_candidate / variant_3 | `out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm` |
| package_rev4_candidate / variant_4 | `out/v4_candidate/hp2170-v4c-v4-tabs-off-sameFace.tbm` |

## `m_dOffsetPosAvg` — Positive Offset (mm)

Two occurrences per file: one in the **Detailed Builder** (DB) block, one in the
**Simple Builder** (SB) block. Both are extracted independently from their respective
`<BUILDER>` sections. The extractor identifies DB vs SB by the header line inside each
`<BUILDER>` block; values from different blocks are never aliased.

| File | DB | SB |
|------|----|----|
| source | 1e-06 | 0 |
| HE18650 | 0.5 | 0 |
| package_rev3 / variant_1 | 1e-06 | 0 |
| package_rev3 / variant_2 | 1e-06 | 0 |
| package_rev3 / variant_3 | 1e-06 | 0 |
| package_rev3 / variant_4 | 1e-06 | 0 |
| package_rev4_candidate / variant_1 | 0.5 | 0 |
| package_rev4_candidate / variant_2 | 0.5 | 0 |
| package_rev4_candidate / variant_3 | 0.5 | 0 |
| package_rev4_candidate / variant_4 | 0.5 | 0 |

**Notes:**

- source DB = `1e-06`, SB = `0`. The DB value was set by About-Energy in the original ECM-mode TBM; it is near-zero but not identically zero. SB = `0` (NOT 0.5 — a prior version of this document incorrectly showed SB = 0.5 for source).
- HE18650 (known-good Siemens stock reference): DB = `0.5`, SB = `0`.
- All package_rev3 variants: DB = `1e-06`, SB = `0`. SB = `0` (NOT 0.5 — prior incorrect claim corrected here).
- package_rev4_candidate all variants: DB = `0.5`, SB = `0`. DB corrected from `1e-06` → `0.5` (CONSISTENCY_FIX: all known-working references use DB = 0.5). SB = `0` (unchanged from source/package_rev3).
- **package_rev4_candidate DB/SB pattern matches HE18650 exactly** (`0.5` / `0`).

## `m_dMandrelWidth` — Mandrel Width (mm)

| File | DB (`m_dMandrelWidth_mm`) | SB (`m_dMandrelWidth`) |
|------|--------------------------|------------------------|
| source | 0 | 0 |
| HE18650 | 5 | 5 |
| package_rev3 / variant_1 | 6 | 0 |
| package_rev3 / variant_2 | 6 | 0 |
| package_rev3 / variant_3 | 6 | 0 |
| package_rev3 / variant_4 | 6 | 0 |
| package_rev4_candidate / variant_1 | 6 | 0 |
| package_rev4_candidate / variant_2 | 6 | 0 |
| package_rev4_candidate / variant_3 | 6 | 0 |
| package_rev4_candidate / variant_4 | 6 | 0 |

## `m_dElectrodeOverlapAtStart` — Electrode Overlap at Start (mm)

| File | DB (`m_dElectrodeOverlapAtStart_mm`) | SB (`m_dElectrodeOverlapAtStart`) |
|------|--------------------------------------|-----------------------------------|
| source | 0 | 8 |
| HE18650 | 30 | 30 |
| package_rev3 / variant_1 | 8 | 8 |
| package_rev3 / variant_2 | 8 | 8 |
| package_rev3 / variant_3 | 8 | 8 |
| package_rev3 / variant_4 | 8 | 8 |
| package_rev4_candidate / variant_1 | 8 | 8 |
| package_rev4_candidate / variant_2 | 8 | 8 |
| package_rev4_candidate / variant_3 | 8 | 8 |
| package_rev4_candidate / variant_4 | 8 | 8 |

source DB = `0` was a placeholder in the source file; the field provenance is unknown. BDS reported "Extrusion distance cannot be 0" for the source geometry test. All package_rev3 and package_rev4_candidate variants have this corrected to `8`.

## `m_bOnly1D` — 1D-only ECM flag (per SIMMOD, document order)

| File | Values |
|------|--------|
| source | `[1, 1, 1, 1]` |
| HE18650 | `[1, 0, 0, 0]` |
| package_rev3 / variant_1 | `[0, 0, 0, 0]` |
| package_rev3 / variant_2 | `[0, 0, 0, 0]` |
| package_rev3 / variant_3 | `[0, 0, 0, 0]` |
| package_rev3 / variant_4 | `[0, 0, 0, 0]` |
| package_rev4_candidate / variant_1 | `[0, 0, 0, 0]` |
| package_rev4_candidate / variant_2 | `[0, 0, 0, 0]` |
| package_rev4_candidate / variant_3 | `[0, 0, 0, 0]` |
| package_rev4_candidate / variant_4 | `[0, 0, 0, 0]` |

**Notes:**

- source: `[1, 1, 1, 1]`. The source was assembled in this workspace from Siemens template material and About-Energy data; provenance of the `m_bOnly1D` values is unknown. BDS reported "Warning: m_bOnly1D option is not supported" during the earlier geometry test.
- HE18650 (known-good): `[1, 0, 0, 0]`. Machine extraction confirms HE18650 **does** contain four `m_bOnly1D` fields. The first SIMMOD (Distributed 3D) retains `m_bOnly1D = 1`; the remaining three are 0. The file builds successfully in BDS, indicating that only certain SIMMOD contexts cause BDS to reject the value. **Prior incorrect claim corrected: an earlier version of this document stated "HE18650 does NOT have the m_bOnly1D field in any of its SIMMOD blocks at all." That statement was false. Machine extraction proves the field is present.**
- All package_rev3 variants: `[0, 0, 0, 0]` — all four zeroed by the generator to clear the BDS "not supported" error.
- All package_rev4_candidate variants: `[0, 0, 0, 0]` — unchanged from package_rev3 (no change needed).

## Active RCRTable 3D — capacity fields

| File | `m_bSpecifyCapacity` | `m_dAhCell` (Ah) |
|------|---------------------|------------------|
| source | 1 | 5.0 |
| HE18650 | 0 | 0 |
| package_rev3 / variant_1 | 1 | 5.0 |
| package_rev3 / variant_2 | 1 | 5.0 |
| package_rev3 / variant_3 | 1 | 5.0 |
| package_rev3 / variant_4 | 1 | 5.0 |
| package_rev4_candidate / variant_1 | 1 | 5.0 |
| package_rev4_candidate / variant_2 | 1 | 5.0 |
| package_rev4_candidate / variant_3 | 1 | 5.0 |
| package_rev4_candidate / variant_4 | 1 | 5.0 |

`m_bSpecifyCapacity = 1` with `m_dAhCell = 5.0 Ah` is the About-Energy NCA 2170 5 Ah specification. Both source and all variants correctly set this. HE18650 has `m_bSpecifyCapacity = 0` because it relies on internal winding geometry to determine capacity rather than an explicit override.
