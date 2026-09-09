# Documentation Index

Index of reference documentation relevant to TBM validation. This document records what documentation exists, where it is, and which specific sections/fields/rules apply to known open questions.

**Do not reproduce copyrighted Siemens documentation text here.** Record only the location and the specific rule/section/page number that applies. Reviewers with STAR-CCM+ access can look up the full text.

---

## Siemens / STAR-CCM+ documentation

### STAR-CCM+ User Guide — Battery Module

**Location:** STAR-CCM+ help system, section: Battery > Battery Module > Template-Based Modeling

**Relevant sections:**
- "Create Battery Module from TBM File" — covers the "File > Create from Tbm" import operation; lists required fields and typical failure modes
- "Detailed Builder" and "Simple Builder" — explains the two winding geometry builder options and their field differences (including whether Detailed or Simple Builder is active when both are present)
- "UnitCellModel SIMMOD blocks" — explains `m_bOnly1D` flag; section title may vary by version. The error "m_bOnly1D option is not supported" originates here.
- "Electrochemical Models > RCR Table" — covers `Set[N]_m_dT`, `Set[N]_RCR_V_*` fields, temperature set structure

**Open question this documentation answers:**
- What is the correct `m_bOnly1D` pattern across SIMMOD blocks for 3D distributed operation?
- When both Simple Builder and Detailed Builder blocks are present, which one drives "Create from Tbm"?
- What is `m_dJellyrollThickness_mm` supposed to represent exactly — JR outer diameter or something else?

**STAR-CCM+ version in Robert's environment:** Unknown (not reported). Field interpretation may vary between versions.

---

### Battery Design Studio (BDS) Reference Manual

**Location:** Siemens BDS plugin documentation; accessible inside BDS or from Siemens support portal

**Relevant sections:**
- Field descriptions for Detailed Builder fields (`m_dJellyrollThickness_mm`, `m_dElectrodeOverlapAtStart_mm`, `m_dElectrodeOverlapAtEnd_mm`, `m_dSepFeedLength_mm`, `m_dSepTailLength_mm`)
- `m_bOnly1D` field description and allowed values per SIMMOD block type
- Mandrel configuration: `m_bMandrelFlat`, `m_dMandrelThickness_mm`, `m_dMandrelWidth_mm`

**Not available in this environment.** We do not have BDS installed. All field-level interpretation is inferred from TBM file inspection and error messages from Robert.

---

### Siemens stock TBM examples

**Location (in this repo):** `tbm_validation/reference/` and `tbm_validation/in_StarCCM_bds/`

These are the primary source of field-level guidance available without Siemens documentation access. See `TBM_STRUCTURAL_COMPARISON.md` for the comparison.

---

## About-Energy documentation and data

### Electrochemical characterisation data — `python/params.csv`

**Location in workspace:** `python/params.csv` (also copied to `data/python_params.csv` in this repo)

**Content:** 7 SOC points × 3 temperatures (15/25/35°C). Columns: `Q_Ah`, `T_degC`, `E_OCV_dch_V`, `E_OCV_ch_V`, `R0_Ohm`, `R_Ohm_1`, `C_F_1`, `R_Ohm_2`, `C_F_2`, `gamma`, `dUdT`

**Used for:** RCR table (`RCRTable 3D` SIMMOD block), OCV curves, entropy term (dU/dT)

**Not used for:** Geometry fields. No electrode geometry data (layer thicknesses, overlap lengths, separator dimensions) is in this file.

### About-Energy communication — tab orientation

**Date:** 2026-09-03 (confirmed with Miles)
**Content:** Both tabs are on top of the cell (same-face terminal configuration). Negative tab orientation = 0 (top), positive tab orientation = 0 (top).

**Used for:** `m_nNegTabVertOrientation = 0`, `m_nPosTabVertOrientation = 0` in production config.

---

## Cell physical reference

### 2170 Battery Cell Thermal Properties Reference

**Location in workspace:** `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md`

**Used fields:**
- External diameter: 21.09 mm → `Package m_dextDiameter`
- External height: 70.02 mm → `Package m_dextHeight`
- Can wall thickness: 0.2313 mm → derivation of `Package m_dintDiameter`
- Jelly-roll active height: 65.11 mm → `Package m_dintHeight`, `-Electrode Collector m_dWidth_mm`
- Positive electrode collector width: 64.11 mm → `+Electrode Collector m_dWidth_mm`

**Not found in this reference:** `m_dJellyrollThickness_mm` (JR OD), electrode overlap lengths, separator dimensions, mandrel details beyond diameter.

---

## Geometry characterization findings (2026-08-31)

The August STEP characterization is recorded in `tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`. It established that Detailed Builder `m_dJellyrollThickness_mm` drives realized jelly-roll diameter, while the tested Simple Builder and REPORT jelly-roll diameter fields were not observed to drive it. It also recorded zero JellyRoll∩Can and JellyRoll∩Mandrel intersection volume in all 20 successful variants.

This finding does not establish the correct physical 2170 winding OD, and it does not replace the separate package-specific import/topology check for the four `package_rev3` variants.

### Robert's STEP file inspection — expected date: after v3 test

**When received:** The August characterization STEP package was received and analyzed on 2026-08-31. The four package-specific `package_rev3` STEP exports are a separate pending result.

**Will answer:**
- Whether BDS generates JellyRoll + Can + EndPlate topology as expected
- Whether m_bOnly1D=0 (all blocks) resolves the v2 import error
- Whether the JellyRoll-Can gap (1.38 mm from `m_dJellyrollThickness_mm = 19.25`) causes visible geometry problem
- Which tab variants produce the desired topology (bottom face clean, top EndPlate only)

**Record findings in `STAR_IMPORT_ERROR_HISTORY.md` when received.**

---

## Existing controlled PDF reports

### TBM Cell Geometry Findings — Rev A

**File:** `artifacts/reports/TBM_CELL_GEOMETRY_FINDINGS_RevA_20260812.pdf`
**Issue date:** 2026-08-12
**Content:** Documents original geometry mismatch findings for the 2170 source TBM. Shows field-level discrepancies vs 2170 cell spec. Predates the v1/v2/v3 geometry test packages.
**SHA-256:** (not recorded here — see document-control section in the PDF itself)
