# Current TBM Field Audit

> **Naming correction (integration review, 2026-09-09):** Bare "V3" replaced with `package_rev3` throughout. "V4" was previously ambiguous — it referred to both variant_4 of package_rev3 and the package_rev4_candidate. This document covers package_rev3 only. See `V4_CANDIDATE_DELTA_REPORT.md` for the package_rev4_candidate.
>
> **SB m_dOffsetPosAvg correction:** The Simple Builder cross-check table row for `m_dOffsetPosAvg` previously listed SB = `0.5`. Machine extraction proves the Simple Builder value is `0` in both source and all package_rev3 variants. Corrected below.
>
> **HE18650 m_bOnly1D correction:** A note in the m_bOnly1D table previously stated "HE18650 does NOT have the m_bOnly1D field in any of its SIMMOD blocks at all." Machine extraction shows HE18650 contains `m_bOnly1D = [1, 0, 0, 0]` (Distributed 3D = 1, remaining three = 0). The table and notes have been corrected.

Field-by-field classification for the package_rev3 variants. Every important field is assigned a status and a risk level for production use.

**Last revised:** 2026-09-09 (independent review of commit e3c3b14; integration corrections applied 2026-09-09 — SB m_dOffsetPosAvg and HE18650 m_bOnly1D narrative corrected from machine extraction)

---

## Status definitions

| Status | Meaning |
|---|---|
| VERIFIED | Value confirmed from About-Energy data, cell datasheet, or Siemens reference that matches at least one known-good TBM |
| ASSUMED | Value not directly confirmed; adopted from a reference or internal logic; must verify before production |
| WARN | Known discrepancy or anomaly; flagged by validator; may or may not cause import failure |
| UNRESOLVED | Value is uncertain; correct value not determinable from available data |
| STALE | Value inherited from old geometry (18650 or older BDS session); will be wrong for 2170 |
| CORRECT | Value confirmed correct and will not need to change |

---

## Package fields

| Field | V3 value | Status | Risk | Notes |
|---|---|---|---|---|
| `m_dextDiameter` | 21.09 mm | VERIFIED | Low | From cell datasheet |
| `m_dextHeight` | 70.02 mm | VERIFIED | Low | From cell datasheet |
| `m_dintDiameter` | 20.6274 mm | VERIFIED | Low | Derived: 21.09 − 2×0.2313 mm |
| `m_dintHeight` | 65.11 mm | VERIFIED | Low | Negative electrode collector width from About-Energy |
| `m_strName` | 2170 | CORRECT | Low | Label only |
| `m_bextVolCalc` | 1 | CORRECT | Low | STAR recalculates at import |
| `m_bintVolCalc` | 1 | CORRECT | Low | STAR recalculates at import |
| `m_dextVolume` | 16.5321 cm³ | STALE | Low | Stale from old 18650 geometry; STAR recomputes (m_bextVolCalc=1) |
| `m_dintVolume` | 14.9232 cm³ | STALE | Low | Same; STAR recomputes |

---

## BUILDER — Detailed Builder fields

| Field | V3 value | Status | Risk | Notes |
|---|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 mm | **UNRESOLVED** | **High** | ~1.38 mm gap to can ID (20.6274 mm). Correct value not confirmed. Do NOT force to can ID without cell teardown data. See STAR_IMPORT_ERROR_HISTORY. |
| `m_dMandrelThickness_mm` | 6 mm | ASSUMED | Medium | Mandrel diameter from TBM source; not confirmed from About-Energy or cell construction data |
| `m_dMandrelWidth_mm` | 6 mm | ASSUMED | Low | Set equal to thickness (cylindrical convention, matches HE18650 where width=thickness=5). Width=0 is also valid (Tutorial ref). This field exists in Detailed Builder only (Simple Builder has separate `m_dMandrelWidth`). |
| `m_bMandrelFlat` | 0 | ASSUMED | Low | Cylindrical mandrel; consistent with all references |
| `m_dElectrodeOverlapAtStart_mm` | 8 mm | ASSUMED | Medium | Matches HP18650-template (8 mm). Copied from Simple Builder in source. Not confirmed from About-Energy electrode spec. |
| `m_dElectrodeOverlapAtEnd_mm` | 20 mm | **UNRESOLVED** | Medium | Lower than all references (HE18650=50, HP18650-templ=30, Tutorial=40). Origin unknown. Not expected to block import but may affect winding geometry. |
| `m_dSepFeedLength_mm` | 0 mm | ASSUMED | Low | Matches HE18650 (also 0); HP18650-templ uses 10. May affect whether separator "wraps" around end. |
| `m_dSepTailLength_mm` | 0 mm | ASSUMED | Low | Same as above |
| `m_dOffsetPosAvg` | 1e-06 | **WARN** | Medium | All known-working references (HE18650, HP18650-templ, Tutorial, LiIonSpiral) use 0.5. HP18650-DIST also uses 1e-06. Provenance of 1e-06 in our source TBM is UNKNOWN. Impact on BDS winding geometry is UNCONFIRMED. Added to high-risk field audit. |
| `m_nNumSpokes` | (inherited) | ASSUMED | Low | Not audited; matches reference structure |

---

## BUILDER — Simple Builder fields (cross-check)

The Simple Builder section contains a second copy of some Detailed Builder fields. STAR-CCM+'s precedence rule (which copy wins during "Create from Tbm") is UNCONFIRMED.

| Field | DB value | SB value | Match? | Notes |
|---|---|---|---|---|
| `m_dElectrodeOverlapAtStart` | 8 mm | 8 mm | ✓ Yes | Consistent after V3 fix |
| `m_dMandrelWidth` | 6 mm | 0 mm | ✗ No | DB≠SB; unknown impact |
| `m_dOffsetPosAvg` | 1e-06 | 0 | ✓ n/a | DB=1e-06, SB=0. Values differ (DB near-zero, SB zero). Prior doc incorrectly showed SB=0.5; machine extraction corrects this. |

---

## m_bOnly1D (per-SIMMOD block)

| SIMMOD block | package_rev3 value | HE18650 value | Status | Notes |
|---|---|---|---|---|
| Distributed 3D | 0 | 1 | ASSUMED | package_rev3 set to 0 (was 1 in source). HE18650 has 1 here; LiIonSpiral/Tutorial/HV-LiCoO2f have 0. References disagree for this block. |
| Distributed | 0 | 0 | ASSUMED | package_rev3 set to 0. HE18650=0 matches. LiIonSpiral/Tutorial have 1. |
| NTGPTable 3D | 0 | 0 | ASSUMED | package_rev3 set to 0. Matches HE18650, HP18650-templ, LiIonSpiral, Tutorial, HV-LiCoO2f. |
| **RCRTable 3D** | **0** | **0** | **VERIFIED** | Active model block. Matches ALL working references: HE18650, HP18650-templ, LiIonSpiral, Tutorial, HV-LiCoO2f. Only HP18650-DIST has 1 (import status unknown). |

**HE18650 m_bOnly1D note (corrected):** Machine extraction confirms HE18650 **does** contain four `m_bOnly1D` fields with values `[1, 0, 0, 0]`. The first SIMMOD block (Distributed 3D) retains `m_bOnly1D = 1`; the remaining three are 0. HE18650 builds successfully in BDS despite Distributed 3D having `m_bOnly1D = 1`, indicating only certain SIMMOD contexts cause BDS to reject the value. A prior version of this document stated "HE18650 does NOT have the m_bOnly1D field in any of its SIMMOD blocks at all" — that was incorrect and has been removed.

The package_rev2 failure was caused by SOURCE having `m_bOnly1D = 1` in all four blocks (including RCRTable 3D). package_rev3 sets all to 0.

---

## Electrochemical — RCRTable 3D block

**IMPORTANT — correct block required for lookup:** Several fields appear in multiple SIMMOD blocks. The values below are from the RCRTable 3D block specifically (active electrochemical model). A flat file scan returns different values. The corrected validator uses block-aware lookup.

| Field | RCRTable 3D value | Status | Notes |
|---|---|---|---|
| `m_bSpecifyCapacity` | 1 | VERIFIED | Capacity explicitly specified (1 = yes) |
| `m_dAhCell` | 5.0 Ah | VERIFIED | From About-Energy `Qnom_Ah = 5.0` in params.csv |
| `m_nRCRParameterSets` | 3 | VERIFIED | 3 temperature sets |
| `Set[0]_m_dT` | 288.15 K | VERIFIED | 15°C from params.csv |
| `Set[1]_m_dT` | 298.15 K | VERIFIED | 25°C |
| `Set[2]_m_dT` | 308.15 K | VERIFIED | 35°C |
| `Set[N]_RCR_V_Ro_*` | See params.csv | VERIFIED | R0 from About-Energy characterisation |
| `Set[N]_RCR_V_Rp_*` | See params.csv | VERIFIED | R1 from About-Energy |
| `Set[N]_RCR_V_tau_*` | See params.csv | VERIFIED | τ1 = R1·C1 from About-Energy |
| `Set[N]_RCR_V_SOC_1` | -0.08 | ASSUMED | Extrapolation point: SOC = 1 − 5.4/5.0. Intentional per translate script. STAR SOC-range tolerance UNCONFIRMED. |

---

## DataSheet fields

These are label/metadata fields. They do NOT affect geometry or physics. They do NOT cause STAR import failures. However, they should be corrected before production for documentation hygiene and to avoid confusion if STAR displays these values in reports.

| Field | V3 value | Expected 2170 value | Status | Priority |
|---|---|---|---|---|
| `m_strName` | HPCell | hp2170NCA | STALE | Fix before production |
| `m_strDSName` | HPCell | hp2170NCA | STALE | Fix before production |
| `m_dHeight` | 65.0 mm | 70.02 mm | STALE (HP18650 residual) | Fix before production |
| `m_dDSHeight` | 65.0 mm | 70.02 mm | STALE (HP18650 residual) | Fix before production |
| `m_dCapacity` | 1.1 Ah | 5.0 Ah | STALE (HP18650 residual) | Fix before production |
| `m_dDSCapacity` | 0.9 Ah | 5.0 Ah | STALE (HP18650 residual) | Fix before production |
| `m_dDSDiameter` | 21.09 mm | 21.09 mm | CORRECT | No change needed |

---

## REPORT block fields

The `<REPORT>` block contains BDS-computed output values from a prior BDS session with the old 18650-like jelly-roll geometry. All fields in our TBM have flag=0 (BDS-computed). `m_dRepCanXDim/YDim/ZDim` are Level-C fields documented as consumed by STAR-CCM+ at import. The remaining `m_dRep*` fields are informational.

| Field | V3 value | Correct value | Status | Consumed by STAR? |
|---|---|---|---|---|
| `m_dRepCanXDim` | 21.09 mm | 21.09 mm | CORRECT | YES (Level-C, documented) |
| `m_dRepCanYDim` | 21.09 mm | 21.09 mm | CORRECT | YES |
| `m_dRepCanZDim` | 70.02 mm | 70.02 mm | CORRECT | YES |
| `m_dRepJellyrollDiameter` | 17.8064 mm | ~19–20 mm (TBD) | STALE | UNCONFIRMED |
| `m_dRepJellyrollHeight` | 52.5 mm | 65.11 mm | STALE | UNCONFIRMED |
| `m_dRepCapacity` | 1.14762 Ah | 5.0 Ah | STALE | UNCONFIRMED (likely recomputed by STAR) |
| `m_dRepActiveArea_m2` | 0.0855507 m² | Depends on geometry | STALE | UNCONFIRMED |

---

## High-risk field audit summary

Fields in this list require special attention before production. These are fields where the current value is either wrong, stale, or its impact is uncertain.

| Field | Current V3 value | Risk | Action required |
|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 mm | **HIGH** | Confirm correct JR OD from cell teardown or AE data. Do NOT force to can ID without evidence. |
| `m_dOffsetPosAvg` (Detailed Builder) | 1e-06 | **MEDIUM** | Investigate provenance. Consider correcting to 0.5 (matches all simple references). Monitor if STAR import behaves differently with 0.5 vs 1e-06. |
| `m_dElectrodeOverlapAtEnd_mm` | 20 mm | **MEDIUM** | Confirm from About-Energy electrode spec. Lower than all references. |
| `m_dElectrodeOverlapAtStart_mm` | 8 mm | **MEDIUM** | Confirm from About-Energy electrode spec. Currently assumed from Simple Builder value; matches HP18650-template. |
| `SOC_min = -0.08` | -0.08 | **MEDIUM** | Verify STAR-CCM+ accepts SOC < 0 in RCR tables. Document intentional extrapolation point. |
| `m_dMandrelThickness_mm` | 6 mm | **LOW-MEDIUM** | Confirm from cell construction data. |
| REPORT stale fields | 18650 geometry | **LOW** | Likely recomputed by STAR during "Create from Tbm"; m_dRepCanXDim/YDim/ZDim are correct. Monitor. |
