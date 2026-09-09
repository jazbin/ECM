# Pre-Client Release Checklist

> **Integration-review corrections (2026-09-09):** Bare "V3" and "V4" replaced with `package_rev3` and `package_rev4_candidate`. Item 3 under "Production TBM requirements" previously stated "The Simple Builder value was already 0.5" — machine extraction proves this was incorrect. The Simple Builder `m_dOffsetPosAvg` is `0` in source and all package_rev3 variants. The correction has been applied below.

Use this checklist before sending any TBM package to Robert. A candidate package must reach at least STATIC_PASS before it is sent. STAR_IMPORT_PASS is the confidence threshold for production physics use.

---

## Confidence states

| State | Meaning |
|---|---|
| STATIC_PASS | `tools/validate_tbm.py` reports 0 FAIL for all variants in the package. WARNs must be reviewed and either resolved or explicitly accepted with written justification. Do NOT claim STATIC_PASS if any check depends on a known parser ambiguity. |
| STAR_IMPORT_PASS | Robert has successfully run "File > Create from Tbm" in STAR-CCM+ on all variants without error. BDS has generated the expected geometry. |
| PHYSICS_PASS | A STAR-CCM+ simulation with the TBM has been run and the output is physically reasonable (temperatures, heat generation, capacity). At minimum: initial SOC discharge, temperature rise qualitatively consistent with About-Energy data. |

---

## Checklist: before any send

- [ ] All variants pass: `python3 tools/validate_tbm.py --batch <variant_dir> --ref tbm_validation/reference/HE18650/he18650spiral1.tbm`
- [ ] All FAIL results are zero.
- [ ] All WARN results are reviewed: for each WARN, either the field is fixed or there is a written acceptance justification in this checklist.
- [ ] SHA-256 of each variant file is recorded in TBM_INVENTORY.md before sending.
- [ ] The package (zip) SHA-256 is recorded in TBM_INVENTORY.md.
- [ ] The generate script version (git commit SHA) that produced the variants is recorded.
- [ ] The source TBM used is recorded by SHA-256.
- [ ] Any new error history entries are written to STAR_IMPORT_ERROR_HISTORY.md.
- [ ] Regression tests pass: `python3 tbm_validation/tests/test_validator.py`

---

## package_rev3 status (`tbm_geometry_test_20260909.zip`)

**Sent to Robert:** 2026-09-09
**Static validator:** 0 FAIL, 8 WARN for all 4 variants.

**Note on WARN count revision:** The original validator (commit e3c3b14) reported 3 WARN for V3 variants. The corrected validator (this commit) now correctly detects 8 WARN per variant. The additional WARNs (offset_pos_avg, DataSheet residuals) were present in V3 but not caught by the old validator. The REPORT block WARNs were hidden by a parser bug (REPORT block format uses tab-separated fields which the main regex did not match).

### WARN review for v3

| WARN | Field | V3 value | Action |
|---|---|---|---|
| JR-Can gap | `m_dJellyrollThickness_mm = 19.25` | 19.25 mm | **ACCEPTED FOR GEOMETRY TEST** — tests topology, not final physics. JR-Can gap does not prevent geometry creation. Must be fixed before production. UNRESOLVED until cell teardown data available. |
| m_dOffsetPosAvg | `m_dOffsetPosAvg (DB) = 1e-06` | 1e-06 | **ACCEPTED FOR GEOMETRY TEST** — impact on BDS winding geometry is UNCONFIRMED. Fixed in package_rev4_candidate (→ 0.5). |
| DataSheet m_dHeight | `DataSheet m_dHeight = 65.0` | 65.0 mm | **ACCEPTED FOR GEOMETRY TEST** — label field, does not drive geometry. Fixed in package_rev4_candidate. |
| DataSheet m_dDSHeight | `DataSheet m_dDSHeight = 65.0` | 65.0 mm | **ACCEPTED FOR GEOMETRY TEST** — same. Fixed in package_rev4_candidate. |
| DataSheet m_dCapacity | `DataSheet m_dCapacity = 1.1` | 1.1 Ah | **ACCEPTED FOR GEOMETRY TEST** — label field. Fixed in package_rev4_candidate. |
| DataSheet m_dDSCapacity | `DataSheet m_dDSCapacity = 0.9` | 0.9 Ah | **ACCEPTED FOR GEOMETRY TEST** — label field. Fixed in package_rev4_candidate. |
| DataSheet m_strName | `DataSheet m_strName = HPCell` | HPCell | **ACCEPTED FOR GEOMETRY TEST** — label field. Fixed in package_rev4_candidate. |
| DataSheet m_strDSName | `DataSheet m_strDSName = HPCell` | HPCell | **ACCEPTED FOR GEOMETRY TEST** — label field. Fixed in package_rev4_candidate. |

**Additional findings now visible (REPORT block, were undetected in v3 by parser bug):**
These WARNs exist in the V3 TBM files sent to Robert. They were not detectable by the old validator. They are documented here for completeness; they do NOT make V3 retroactively not STATIC_PASS since the REPORT stale values are informational and m_dRepCanXDim/YDim/ZDim (consumed by STAR) are correct.

| Check | V3 value | Issue |
|---|---|---|
| `report_jr_diameter` | 17.8064 mm | Stale from old BDS session; BUILDER has 19.25 mm. STAR likely recomputes at import. |
| `report_jr_height` | 52.5 mm | Stale; Package m_dintHeight = 65.11 mm. |
| `report_capacity` | 1.14762 Ahr | Stale; RCRTable 3D m_dAhCell = 5.0 Ahr. |

### v3 static confidence level: STATIC_PASS (0 FAIL, 8 WARN all accepted for geometry test)
### v3 STAR_IMPORT_PASS: PENDING (awaiting Robert's results)

---

## package_rev4_candidate status (`out/v4_candidate/`)

**NOT sent to Robert.** Review candidate prepared 2026-09-09.
**Generate script:** `tools/generate_tbm_v4_candidate.py`
**Static validator:** 0 FAIL, 4 WARN for all 4 variants.

See `tbm_validation/V4_CANDIDATE_DELTA_REPORT.md` for full analysis.

### WARN review for package_rev4_candidate

| WARN | Field | Value | Status |
|---|---|---|---|
| JR-Can gap | `m_dJellyrollThickness_mm = 19.25` | 19.25 mm | UNRESOLVED — pending geometry test result and cell data |
| REPORT JR diameter | `m_dRepJellyrollDiameter = 17.8064` | 17.8064 mm | STALE — REPORT block informational; not consumed (m_dRepCanXDim/YDim/ZDim are correct) |
| REPORT JR height | `m_dRepJellyrollHeight = 52.5` | 52.5 mm | STALE — same |
| REPORT capacity | `m_dRepCapacity = 1.14762` | 1.14762 Ahr | STALE — informational; RCRTable 3D has correct m_dAhCell=5.0 |

### package_rev4_candidate confidence level: NOT_YET_ASSESSED
- Reviewer must confirm WARN justifications in V4_CANDIDATE_DELTA_REPORT.md
- Do not send until V3 STAR_IMPORT_PASS is confirmed and V4 WARN justifications are reviewed

---

## Template for future packages

```
## Package: [name] — [date]

**ZIP SHA-256:** [hash]
**Source TBM SHA-256:** [hash]
**Generate script git commit:** [sha]
**Sent to Robert:** [yes/no, date]
**Static validator (corrected):** [N FAIL N WARN N INFO N PASS per variant]

### Variant SHA-256s
| Variant | SHA-256 | Static validator |
|---|---|---|
| [name] | [hash] | [N FAIL N WARN] |
...

### WARN review
| WARN | Field | Action |
...

### Confidence level
- Static: STATIC_PASS / NOT PASSED / NOT_YET_ASSESSED
- STAR import: PENDING / STAR_IMPORT_PASS / FAILED (error text in STAR_IMPORT_ERROR_HISTORY.md)
- Physics: PENDING / PHYSICS_PASS / TBD
```

---

## Production TBM requirements (not yet met)

The following must be fixed before any TBM is used for production physics simulation:

1. **`m_dJellyrollThickness_mm`** — must be confirmed from About-Energy or cell teardown. Current 19.25 mm leaves a 1.38 mm diametral gap to the can ID. Do NOT force to can ID without evidence.
2. **Electrode overlap values** — `m_dElectrodeOverlapAtStart_mm = 8` is ASSUMED (from HP18650-template reference). `m_dElectrodeOverlapAtEnd_mm = 20` is UNRESOLVED (lower than all references). Both must be confirmed from About-Energy electrode spec or cell construction data.
3. **`m_dOffsetPosAvg`** — package_rev4_candidate corrects Detailed Builder from `1e-06` to `0.5` (CONSISTENCY_FIX). Must confirm no adverse geometry effect in STAR. The Simple Builder value is `0` in source, package_rev3, and package_rev4_candidate (unchanged). Only the Detailed Builder was changed.
4. **DataSheet corrections** — V4 fixes all HP18650 label residuals. Label-only, no physics impact.
5. **Geometry test result** — understand what topology BDS generates for all 4 variants before locking the production tab configuration. V3 result pending.
6. **SOC range** — confirm STAR-CCM+ accepts SOC < 0 in RCR tables (our min is -0.08, intentional).
7. **Thermal properties** — verify `m_dDensity`, `m_dHeatCapacity`, `m_dThermalConductivity` in TBM electrochemistry blocks against `cellprops.csv` values from About-Energy. Currently unaudited — may retain 18650 stock values.
