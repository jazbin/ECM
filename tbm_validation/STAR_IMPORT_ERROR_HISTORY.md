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
`m_bOnly1D = 1` was present in all 24 SIMMOD blocks of the source TBM. The source file was assembled in this workspace from Siemens template material and About-Energy data; provenance of the flag values is unknown. The repository records an import warning for this source pattern, but exact STAR-CCM+/BDS support by SIMMOD context is unconfirmed.

**Per-SIMMOD-block analysis:**
The error message "Warning: m_bOnly1D option is not supported" appears per-block, not per-file. Two instances were reported — BDS may only report the first N instances or may report for specific blocks (e.g. the two 3D blocks that have explicit 3D geometry creation).

The critical block is `RCRTable 3D` — our active electrochemical model. All known-working references (HE18650, HP18650-template, LiIonSpiral, Tutorial, HV-LiCoO2f) have `m_bOnly1D = 0` or absent in the RCRTable 3D block. Only HP18650-DIST has 1 in RCRTable 3D — its successful import status is UNCONFIRMED.

For the `Distributed 3D` block, references disagree: HE18650 and HP18650-template use 1; LiIonSpiral, Tutorial, HV-LiCoO2f use 0. It is possible BDS only reports the warning for `Distributed 3D` block (the explicit 3D geometry block), not all blocks.

**Fix applied in package_rev3:**
All `m_bOnly1D` occurrences set to 0 via `sub_all()`. package_rev3 has `m_bOnly1D = 0` in all 24 SIMMOD blocks.

**Per-SIMMOD table for package_rev3:**
| SIMMOD block | package_rev3 | HE18650 | HP18650-templ | LiIonSpiral | Tutorial |
|---|---|---|---|---|---|
| Distributed 3D | 0 | 1 | 1 | 0 | 0 |
| Distributed | 0 | 0 | false | true | true |
| NTGPTable 3D | 0 | 0 | 0 | 0 | 0 |
| RCRTable 3D | 0 | 0 | 0 | 0 | 0 |

**Open question:** HE18650 and HP18650-template have `m_bOnly1D = 1` in the Distributed 3D block, yet are known-good references. The warning trigger by SIMMOD context is unconfirmed. The package_rev2 result may relate to the RCRTable 3D block (the active model). package_rev3's all-zero pattern is a conservative project choice, and is consistent with LiIonSpiral and Tutorial reference files.

**Validator check:** `m_bOnly1D_rcrtable` → PASS if RCRTable 3D block has 0 or false.

---

## Error 3 — RCR distributed V1 candidate (2026-09-09)

**Package:** `hp2170-rcr-v1-tabs-on-sameFace.tbm` (RCR distributed candidate V1)
**TBM file SHA-256:** `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940`
**Error text (verbatim from Robert):**
```
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
```
**STAR-CCM+ operation:** File > Create from Tbm

**Diagnosis:**
`+Electrode m_dS3 = 0` in the Detailed Builder electrode section. This field defines a geometric segment at the positive electrode root (Electrode 1 in STAR convention). All 4 STAR-installation cylindrical reference TBMs (validationBattery, testTBM, LiIonSpiral, tutorialCylindricalCell) and HE18650 use `+Electrode m_dS3 = 5`. The BDS-generated source TBM (hp18650Spiral1.tbm, the project clone template) had S3=0, left as a 1D-mode placeholder — the same pattern as the prior `m_dElectrodeOverlapAtStart_mm = 0` placeholder (Error 1). None of the V3/V4 generator scripts had corrected this field until 2026-09-10.

The exact internal STAR mapping of `m_dS3` to the "Electrode Root 1" extrusion feature is inferred from the pattern; not proven until V2 passes runtime import.

**Fix applied in V2:**
`+Electrode m_dS3 = 0 → 5` (added to `apply_v3_fixes()` in `generate_tbm_v4_candidate.py`).

V2 candidate: `out/rcr_candidate/hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm`
V2 SHA-256: `372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b`
Client package: `out/hp2170NCA-RCR-STAR-import-test-S3fix-20260910.zip`

**Validator check added:** `pos_electrode_s3` → FAIL if `+Electrode m_dS3 = 0`. See `validate_tbm.py`.

---

## Error 3a — package_rev3 geometry test (2026-09-09)

**Package:** `tbm_geometry_test_20260909.zip` (package_rev3)
**STAR_IMPORT_PASS status:** **PENDING** — awaiting confirmation from Robert. This was sent 2026-09-09 but superseded by the RCR V1 failure (Error 3 above) on the same date. Status unknown.

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
