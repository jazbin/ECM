# RCR Candidate V1 → V2 S3 Geometry Delta
**Date:** 2026-09-10
**Branch:** tbm-rcr-modelmap-fix-exec
**Authorized by:** `tbm_validation/STAR_GEOMETRY_COMPATIBILITY_AUDIT_20260910.md`

---

## Files

| Version | Path | SHA-256 |
|---|---|---|
| V1 (Robert-tested baseline) | `out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm` | `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940` |
| V2 (S3 geometry fix) | `out/rcr_candidate/hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm` | `372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b` |

V1 was tested by Robert and failed with:
```
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
```

---

## Semantic Delta — Exactly One Field Changed

```
diff V1 V2 (line 1024):
< 	+Electrode m_dS3	=	0	!		!	S3, mm
---
> 	+Electrode m_dS3	=	5
```

**Change:** `+Electrode m_dS3` from `0` to `5` mm.

This is the only semantic change. The trailing inline comment (`!  ! S3, mm`) was removed by the generator regex — this is the same behavior applied to all generator-patched fields in the V3/V4 pipeline (`m_dElectrodeOverlapAtStart_mm`, `m_dMandrelWidth_mm`, etc.). It does not affect parsing.

---

## Byte-level Summary

| Property | Value |
|---|---|
| V1 file size | 304,320 bytes |
| V2 file size | 304,308 bytes |
| Size difference | 12 bytes (trailing inline comment removed from the changed line) |
| Diff line count | 1 line changed (unified diff: 2 diff lines shown) |

---

## Parity Verification

### Positive-electrode S3

| File | +Electrode m_dS3 |
|---|---|
| V1 | **0 mm** |
| V2 | **5 mm** ← fixed |

### Negative-electrode S3 (unchanged)

| File | -Electrode m_dS3 |
|---|---|
| V1 | 50 mm |
| V2 | 50 mm ← identical |

### RCR numerical data

Machine comparison of the full `RCRTable 3D` SIMMOD block (14,663 bytes each):

```
RCR block identical: True
V1 RCR block len: 14663
V2 RCR block len: 14663
```

**All RCR tables, OCV curves, temperature sets, R0/R1/τ values are bit-identical.**

### MODELMAP

Machine comparison of the full `<MODELMAP>` block:

```
MODELMAP identical: True
IET in V2: RCRTable 3D
```

Both V1 and V2 have `IET = RCRTable 3D`. MODELMAP is bit-identical.

### Builder geometry (fields other than +Electrode m_dS3)

These were not changed by the S3 fix. All values verified by diff — no other builder field appears in the diff output:

| Field | V1 value | V2 value |
|---|---|---|
| `m_dElectrodeOverlapAtStart_mm` | 8 mm | 8 mm |
| `m_dElectrodeOverlapAtEnd_mm` | 20 mm | 20 mm |
| `m_dJellyrollThickness_mm` | 19.25 mm | 19.25 mm |
| `m_dMandrelThickness_mm` | 6 mm | 6 mm |
| `m_dMandrelWidth_mm` | 6 mm | 6 mm |
| `m_dSepFeedLength_mm` | 0 mm | 0 mm |
| `m_dSepTailLength_mm` | 0 mm | 0 mm |
| `m_dOffsetPosAvg` | 0.5 | 0.5 |
| `-Electrode m_dS3` | 50 mm | 50 mm |
| `+Electrode m_dS1` | 5 mm | 5 mm |
| `+Electrode m_dS2` | 7 mm | 7 mm |

### Tab configuration

Both V1 and V2 are the "tabs-on-sameFace" variant:
- `m_bNegTab = 1`, `m_bPosTab = 1` (tabs enabled)
- `m_nNegTabVertOrientation = 0` (top, same face)
- `m_nPosTabVertOrientation = 0` (top)

### m_bOnly1D

All 4 SIMMOD blocks: `m_bOnly1D = 0` in both V1 and V2. Identical.

### Package dimensions

Unchanged. `m_dextDiameter = 21.09`, `m_dextHeight = 70.02`, `m_dintDiameter = 20.6274`, `m_dintHeight = 65.11`. Identical between V1 and V2.

---

## Static Validation Results

### V2 (hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm)

```
RESULT: 0 FAIL | 4 WARN | 14 INFO | 36 PASS
```

New passing checks in V2:
- `[PASS] pos_electrode_s3: +Electrode m_dS3 = 5.0 mm. STAR cylindrical references use 5 mm.`
- `[PASS] neg_electrode_s3: -Electrode m_dS3 = 50.0 mm (nonzero; consistent with STAR references).`

### V1 (hp2170-rcr-v1-tabs-on-sameFace.tbm) — for comparison

```
RESULT: 1 FAIL | 4 WARN | 14 INFO | 35 PASS
```

New FAIL triggered in V1 by the regression guard:
- `[FAIL] pos_electrode_s3: +Electrode m_dS3 = 0. ...`

The 4 WARNs in both files are pre-existing and unrelated to S3:
1. `pkg_id_vs_jr` — JR OD vs can ID gap (unresolved)
2. `report_jr_diameter` — stale REPORT value
3. `report_jr_height` — stale REPORT value
4. `report_capacity` — stale REPORT capacity

---

## Generation Lineage

```
Source: tbm_validation/source/hp2170NCA-ECM.tbm
  SHA-256: fa4cb299fc444a35875b51bb0093fae43b88f78a677b92554d732cc72cae6204

  → generate_tbm_v4_candidate.py (V3+V4 fixes, now includes +Electrode m_dS3 = 5)
      → out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm
           SHA-256: e645ab18ad5da81b8a90646743051e8a2e3259d745a2d683589154ad68c12b26

  → generate_tbm_rcr_candidate.py (MODELMAP IET: Distributed 3D → RCRTable 3D)
      → out/rcr_candidate/hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm
           SHA-256: 372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b
```

---

## V1 Preservation

`out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm` was **not modified**. Its SHA-256 remains `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940`. It is retained as the Robert-tested runtime evidence baseline.

---

## Open Item

V2 is a static fix candidate. Whether `+Electrode m_dS3 = 5` resolves the "Electrode Root 1 : Extrusion distance can not be 0" error is UNCONFIRMED until Robert runs `Create from Tbm` on V2 and reports the result. The S3=0→5 change is the single most strongly supported hypothesis from the geometry audit, but the internal STAR mapping of S3 to this specific feature has not been directly documented.
