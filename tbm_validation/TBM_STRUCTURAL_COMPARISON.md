# TBM Structural Comparison

All values in this document are **machine-extracted** directly from the TBM files in this repository using Python scripts. No values are manually transcribed. Where a previous version of this document had manually-transcribed values that differed from machine extraction, the machine-extracted values take precedence.

**Extraction date:** 2026-09-09 (revised in independent review of commit e3c3b14)

---

## Files compared

| Label | File path |
|---|---|
| SOURCE | `tbm_validation/source/hp2170NCA-ECM.tbm` |
| V3 (typical) | `tbm_validation/variants/v3_package_20260909/hp2170-test-v1-tabs-on-standard.tbm` |
| HE18650 | `tbm_validation/reference/HE18650/he18650spiral1.tbm` |
| HP18650-templ | `tbm_validation/reference/GapExample/hp18650Spiral1.tbm` |
| HP18650-DIST | `tbm_validation/reference/CompareChem/hp18650Spiral1.tbm` |
| Tutorial | `tbm_validation/in_StarCCM_bds/tutorialCylindricalCell.tbm` |
| LiIonSpiral | `tbm_validation/in_StarCCM_bds/LiIonSpiral/LiIonSpiral.tbm` |

---

## Package fields

| Field | SOURCE | V3 | HE18650 | HP18650-templ | Notes |
|---|---|---|---|---|---|
| `Package m_dextDiameter` | 21.09 | 21.09 | 18 | 18.4 | 2170 OD = 21.09 mm ✓ |
| `Package m_dextHeight` | 70.02 | 70.02 | 65 | 65 | 2170 height = 70.02 mm ✓ |
| `Package m_dintDiameter` | 17.8 | 20.6274 | 17.8 | 17.8 | V3 corrected to can ID; source retains old value |
| `Package m_dintHeight` | 60 | 65.11 | 60 | 60 | V3 corrected to JR active height; source retains old |
| `Package m_strName` | 18650 | 2170 | 18650 | HP18650 | V3 corrected |
| `Package m_bextVolCalc` | 1 | 1 | 1 | 1 | STAR recalculates external volume |
| `Package m_bintVolCalc` | 1 | 1 | 1 | 1 | STAR recalculates internal volume |

---

## BUILDER — Detailed Builder fields

Machine-extracted from the `<BUILDER>` block (Detailed Builder section). For fields that appear twice in the file (Detailed Builder and Simple Builder), this table shows the Detailed Builder value (index 0 = first occurrence in the BUILDER block).

| Field | SOURCE (DB) | V3 (DB) | HE18650 (DB) | HP18650-templ (DB) | Tutorial (DB) | Notes |
|---|---|---|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 | 19.25 | 17.41 | 17.8 | 13.7 | Our V3 value UNRESOLVED: ~1.38 mm gap to can ID |
| `m_dMandrelThickness_mm` | 6 | 6 | 5 | 6 | 3 | V3 matches HP18650-templ; plausible for 2170 mandrel |
| `m_dMandrelWidth_mm` | 0 | 6 | 5 | 0 | 0 | See note below. V3 was corrected from source 0 |
| `m_bMandrelFlat` | 0 | 0 | 0 | 0 | 0 | Cylindrical mandrel; width=0 is valid ✓ |
| `m_dElectrodeOverlapAtStart_mm` | **0** | **8** | 30 | 8 | 3 | Source had 0 (→ FAIL). V3 corrected. HP18650-templ = 8 |
| `m_dElectrodeOverlapAtEnd_mm` | 20 | 20 | 50 | 30 | 40 | V3 value lower than all refs. Origin UNCONFIRMED |
| `m_dSepFeedLength_mm` | 0 | 0 | 0 | 10 | n/a | Zero matches HE18650; HP18650-templ uses 10 |
| `m_dSepTailLength_mm` | 0 | 0 | 0 | 10 | n/a | Same as above |
| `m_dOffsetPosAvg` | 1e-06 | 1e-06 | 0.5 | 0.5 | 0.5 | **WARN** — all simple refs use 0.5; 1e-06 also in HP18650-DIST |

**Note on `m_dMandrelWidth_mm = 0`:** An earlier version of this document incorrectly stated HE18650 has no `m_dMandrelWidth_mm`. Machine extraction confirms HE18650 Detailed Builder has `m_dMandrelWidth_mm = 5` (= mandrel thickness). HP18650-templ and Tutorial both have width=0. Tutorial also has mandrel thickness=3 with width=0 — confirming that `width=0` is valid for a cylindrical mandrel (`m_bMandrelFlat=0`). V3 was corrected from source 0 to 6 (= mandrel thickness), matching HE18650's width=thickness convention.

---

## BUILDER — Simple Builder fields

The TBM file contains a second set of geometry fields in the Simple Builder section. For fields that appear in both sections, STAR-CCM+'s behaviour (which builder takes priority during "Create from Tbm") is UNCONFIRMED. Machine extraction of the Simple Builder occurrence (index 1):

| Field | SOURCE (SB) | V3 (SB) | HE18650 (SB) | HP18650-templ (SB) | Notes |
|---|---|---|---|---|---|
| `m_dElectrodeOverlapAtStart` | 8 | 8 | — | 8 | Simple Builder used 8 in source; Detailed Builder had 0 |
| `m_dMandrelWidth` | 0 | 0 | — | 0 | Simple Builder; Detailed Builder was corrected to 6 in V3 |
| `m_dOffsetPosAvg` | 0.5 | 0.5 | 0.5 | 0.5 | Simple Builder value is 0.5 in source and V3 |

**Cross-check note:** The `m_dOffsetPosAvg` field shows `1e-06` in the Detailed Builder but `0.5` in the Simple Builder for both SOURCE and V3. If STAR uses the Detailed Builder section, the 1e-06 value applies. If Simple Builder, 0.5 applies. This ambiguity is unresolved.

---

## m_bOnly1D per-SIMMOD block (machine-extracted)

This is the authoritative per-block table from machine extraction. An earlier version of this document described a "global all-one" pattern — that description was inaccurate. The correct analysis is per-block.

| SIMMOD block | SOURCE | V3 | HE18650 | HP18650-templ | HP18650-DIST | LiIonSpiral | Tutorial | HV-LiCoO2f |
|---|---|---|---|---|---|---|---|---|
| Distributed 3D | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 |
| Distributed | 1 | 0 | 0 | false | 1 | true | true | false |
| NTGPTable 3D | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| **RCRTable 3D** | **1** | **0** | **0** | **0** | **1** | **0** | **0** | **0** |

**Active model block: `RCRTable 3D`.** For 3D distributed operation, `m_bOnly1D = 0` is required. V3 has 0 in all blocks. All known-working references (HE18650, HP18650-template, LiIonSpiral, Tutorial, HV-LiCoO2f) have 0 in RCRTable 3D. The V2 package failure ("Warning: m_bOnly1D option is not supported" ×2) was caused by all blocks having 1 (inherited from SOURCE), not by a specific block-level issue.

**HE18650 note:** HE18650 does NOT have the `m_bOnly1D` field in any of its SIMMOD blocks at all — the field is simply absent. The table above shows the extracted value for HE18650 as 0, which is what the validator treats as equivalent (no field = assume 0). HE18650 was successfully imported by Siemens and is the primary reference for a working TBM.

---

## Electrochemical — RCRTable 3D block (machine-extracted)

| Field | SOURCE | V3 | HE18650 | Notes |
|---|---|---|---|---|
| `m_bSpecifyCapacity` | 1 | 1 | — | V3 explicitly sets capacity via m_dAhCell |
| `m_dAhCell` | 5.0 | 5.0 | — | Nominal capacity from About-Energy: 5 Ah |
| `m_nRCRParameterSets` | 3 | 3 | — | 3 temperature sets |
| `Set[0]_m_dT` | 288.15 | 288.15 | — | 15°C in Kelvin |
| `Set[1]_m_dT` | 298.15 | 298.15 | — | 25°C |
| `Set[2]_m_dT` | 308.15 | 308.15 | — | 35°C |
| SOC range | [-0.08, 1.0] | [-0.08, 1.0] | [0, 1] | -0.08 = 1 - 5.4/5.0 extrapolation point; intentional |

**Important:** the `m_bSpecifyCapacity` and `m_dAhCell` fields appear in multiple SIMMOD blocks. A flat file scan returns the first occurrence (which may be from a different block). Capacity validation MUST use block-aware lookup targeting RCRTable 3D. The earlier validator version (commit e3c3b14) used flat scan and generated a false WARN claiming capacity was not specified — the value was correctly set in the RCRTable 3D block.

---

## DataSheet fields (machine-extracted)

The DataSheet section contains informational/label fields. The generate script does NOT currently update these fields, so all V3 variants inherit the HP18650 stock values.

| Field | SOURCE | V3 | Expected 2170 | Notes |
|---|---|---|---|---|
| `DataSheet m_strName` | HPCell | HPCell | hp2170NCA | Stale HP18650 label |
| `DataSheet m_strDSName` | HPCell | HPCell | hp2170NCA | Stale HP18650 label |
| `DataSheet m_dHeight` | 65 | 65 | 70.02 | HP18650 can height; stale |
| `DataSheet m_dDSHeight` | 65 | 65 | 70.02 | Same |
| `DataSheet m_dCapacity` | 1.1 | 1.1 | 5.0 | HP18650 capacity; stale |
| `DataSheet m_dDSCapacity` | 0.9 | 0.9 | 5.0 | Same |
| `DataSheet m_dDSDiameter` | 21.09 | 21.09 | 21.09 | Already correct ✓ |

These are label fields only (not geometry or physics inputs). They do not cause import failure. All must be corrected before a production send.

---

## REPORT block (machine-extracted, from V3 variant)

The `<REPORT>` block contains BDS-computed output values from a prior BDS session with old geometry (18650-like JR dimensions). Fields with flag=0 (all fields in our file) are BDS-computed. STAR-CCM+ may or may not re-use these values at import.

| Field | V3 value | Correct 2170 value | Status |
|---|---|---|---|
| `m_dRepCanXDim` | 21.09 | 21.09 | Correct (set by translate_tbm script) |
| `m_dRepCanYDim` | 21.09 | 21.09 | Correct |
| `m_dRepCanZDim` | 70.02 | 70.02 | Correct |
| `m_dRepJellyrollDiameter` | 17.8064 | ~20.6 mm | STALE — old 18650 geometry. Not consumed by translate_tbm. |
| `m_dRepJellyrollHeight` | 52.5 | 65.11 | STALE — old 18650 geometry |
| `m_dRepCapacity` | 1.14762 | 5.0 | STALE — old 18650 geometry |
| `m_dRepActiveArea_m2` | 0.0855507 | TBD | STALE — will change when JR geometry is corrected |

**`m_dRepCanXDim/YDim/ZDim` are Level-C fields** consumed by STAR-CCM+ at import (confirmed by `translate_tbm_from_openfoam.py`). These are correct in V3. The remaining `m_dRep*` fields are informational/cached — STAR likely recomputes them during "Create from Tbm", but this is UNCONFIRMED.

---

## Key differences: V3 vs SOURCE

This table summarises what the generate script (`tools/generate_tbm_test_variants.py`) changed from SOURCE to produce V3 variants. Everything not listed here is unchanged.

| Field | SOURCE value | V3 value | Fix type | Status |
|---|---|---|---|---|
| `Package m_dintDiameter` | 17.8 | 20.6274 | Geometry correction | Correct |
| `Package m_dintHeight` | 60 | 65.11 | Geometry correction | Correct |
| `Package m_strName` | 18650 | 2170 | Label correction | Correct |
| `m_dElectrodeOverlapAtStart_mm` | 0 | 8 | FAIL fix | Correct (matches HP18650-templ) |
| `m_dMandrelWidth_mm` | 0 | 6 | Geometry fix | Correct (= mandrel thickness) |
| `m_bOnly1D` | 1 (all blocks) | 0 (all blocks) | FAIL fix | Correct |
| `m_nNegTabVertOrientation` | varies | variant-specific | Tab test config | Variant-dependent |
| `m_bNegTab` / `m_bPosTab` | varies | variant-specific | Tab test config | Variant-dependent |

---

## Remaining open items in V3 (not geometry-test blockers, must fix for production)

| Field | V3 value | Issue | Severity |
|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 | ~1.38 mm gap to can ID | UNRESOLVED_ASSUMPTION — correct value not confirmed |
| `m_dOffsetPosAvg` (Detailed Builder) | 1e-06 | All simple refs = 0.5 | WARN — provenance unknown, impact UNCONFIRMED |
| DataSheet fields | HP18650 stock | Stale labels | CONSISTENCY_FIX — label fields only, no import impact |
| SOC min = -0.08 | -0.08 | Extrapolation beyond [0,1] | INFO — intentional, STAR tolerance UNCONFIRMED |
| REPORT stale fields | 18650 geometry | JR diam, height, capacity stale | INFO — may be recomputed by STAR; m_dRepCanXDim/YDim/ZDim are correct |
| `m_dElectrodeOverlapAtEnd_mm` | 20 | Lower than all references | INFO — unconfirmed value, not expected to cause import failure |
