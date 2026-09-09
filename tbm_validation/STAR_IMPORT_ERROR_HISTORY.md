# STAR-CCM+ / BDS Import Error History

Record of every known STAR-CCM+ or BDS import failure for this project's TBM files. Each entry is linked to the specific TBM file (by SHA-256) that triggered the error.

Do not delete or modify historical entries. Add new entries as they occur.

---

## Error 1 — V1 package (2026-09-04)

**Package:** `consultant_dt_sensitivity_20260505.zip` → `tbm_geometry_test_20260904.zip` (v1)
**TBM file SHA-256:** (v1 variants — not recorded, predates SHA-256 audit)
**Error text (verbatim from Robert):**
```
Electrode Root 1 : Extrusion distance can not be 0
```
**STAR-CCM+ operation:** File > Create from Tbm

**Diagnosis:**
`m_dElectrodeOverlapAtStart_mm` in the Detailed Builder section was `0`. BDS requires a positive extrusion distance to create the winding geometry. The source TBM (hp2170NCA-ECM.tbm) had this field set to 0 in the Detailed Builder block — a placeholder left over from the original 18650 template when the TBM was generated in 1D-only mode.

The correct value (8 mm) was already present in the Simple Builder section (`m_dElectrodeOverlapAtStart = 8`) of the same source TBM, but BDS reads the Detailed Builder value.

**Fix applied in V2:**
`m_dElectrodeOverlapAtStart_mm` → 8 mm (Detailed Builder).

The V2 generate script explicitly copies the Simple Builder value to Detailed Builder:
```
m_dElectrodeOverlapAtStart_mm = 8  (copied from Simple Builder; Detailed Builder had 0)
```

**HE18650 reference value:** 30 mm
**HP18650-template reference value:** 8 mm (matches our fix)
**Tutorial reference value:** 3 mm

**Validator check:** `overlap_start` → FAIL if Detailed Builder value is 0.

---

## Error 2 — V2 package (2026-09-07)

**Package:** `tbm_geometry_test_20260907.zip` (v2)
**TBM file SHA-256:** (V2 variants — recorded in TBM_INVENTORY.md)
**Error text (verbatim from Robert):**
```
Warning: m_bOnly1D option is not supported
Warning: m_bOnly1D option is not supported
```
(Two instances reported; total number in file was not stated by Robert)
**STAR-CCM+ operation:** File > Create from Tbm

**Diagnosis:**
`m_bOnly1D = 1` was present in all 24 SIMMOD blocks of the source TBM. The source file was generated with the 1D-only electrochemical mode flag set (likely during the initial BDS session with About-Energy where the emphasis was on 1D ECM, not 3D distributed). STAR-CCM+'s "Create from Tbm" operation for 3D geometry creation does not support the 1D-only mode.

**Per-SIMMOD-block analysis:**
The error message "Warning: m_bOnly1D option is not supported" appears per-block, not per-file. Two instances were reported — BDS may only report the first N instances or may report for specific blocks (e.g. the two 3D blocks that have explicit 3D geometry creation).

The critical block is `RCRTable 3D` — our active electrochemical model. All known-working references (HE18650, HP18650-template, LiIonSpiral, Tutorial, HV-LiCoO2f) have `m_bOnly1D = 0` or absent in the RCRTable 3D block. Only HP18650-DIST has 1 in RCRTable 3D — its successful import status is UNCONFIRMED.

For the `Distributed 3D` block, references disagree: HE18650 and HP18650-template use 1; LiIonSpiral, Tutorial, HV-LiCoO2f use 0. It is possible BDS only reports the warning for `Distributed 3D` block (the explicit 3D geometry block), not all blocks.

**Fix applied in V3:**
All `m_bOnly1D` occurrences set to 0 via `sub_all()`. V3 has `m_bOnly1D = 0` in all 24 SIMMOD blocks.

**Per-SIMMOD table for V3:**
| SIMMOD block | V3 | HE18650 | HP18650-templ | LiIonSpiral | Tutorial |
|---|---|---|---|---|---|
| Distributed 3D | 0 | 1 | 1 | 0 | 0 |
| Distributed | 0 | 0 | false | true | true |
| NTGPTable 3D | 0 | 0 | 0 | 0 | 0 |
| RCRTable 3D | 0 | 0 | 0 | 0 | 0 |

**Open question:** HE18650 and HP18650-template have `m_bOnly1D = 1` in the Distributed 3D block, yet (presumably) import successfully. This suggests the error is NOT triggered by the Distributed 3D block having 1. The error in V2 was more likely triggered by having 1 in the RCRTable 3D block (the active model). V3's all-zero pattern is therefore more conservative than needed, but is consistent with LiIonSpiral and Tutorial (STAR-install TBMs known to work).

**Validator check:** `m_bOnly1D_rcrtable` → PASS if RCRTable 3D block has 0 or false.

---

## Error 3 — V3 package (2026-09-09)

**Package:** `tbm_geometry_test_20260909.zip` (v3)
**STAR_IMPORT_PASS status:** **PENDING** — awaiting confirmation from Robert.

No errors reported as of 2026-09-09 (package just sent). When Robert reports results, add an entry here.

---

## Template for new entries

```
## Error N — [package name] ([date])

**Package:** [filename]
**TBM file SHA-256:** [hash of the specific TBM that failed, from TBM_INVENTORY.md]
**Error text (verbatim from Robert):**
```
[paste exact error text]
```
**STAR-CCM+ operation:** [File > Create from Tbm / Run Physics / Other]

**Diagnosis:**
[What field or value caused the error. Which reference TBM was checked. What the correct value is.]

**Fix applied:**
[What was changed and in which package version]

**Validator check added:**
[Which check in validate_tbm.py now catches this. If none, note the gap.]
```
