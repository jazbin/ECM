# Current TBM Field Audit

Classification of every important field in the current v3 variants (`tbm_validation/variants/v3_package_20260909/`). All four v3 variants are identical in these fields (they differ only in `m_bNegTab`, `m_bPosTab`, `m_nNegTabVertOrientation`).

Confidence levels:
- **VERIFIED_FROM_ABOUT_ENERGY** — value comes from About-Energy characterisation data (`python/params.csv` or direct communication) and has been cross-checked
- **VERIFIED_FROM_CELL_REFERENCE** — value confirmed from cell datasheet, physical measurement, or external reference document
- **VERIFIED_FROM_SIEMENS_REFERENCE** — value matches known-good Siemens TBM reference
- **COPIED_FROM_KNOWN_GOOD_TEMPLATE** — value taken from Siemens stock TBM without independent verification
- **DERIVED** — calculated from other verified values (show formula)
- **ASSUMED** — value chosen without direct verification; assumption documented
- **UNKNOWN** — origin unclear; value retained from source without any verification

---

## Package block

| Field | Value | Classification | Notes |
|---|---|---|---|
| `Package m_dextDiameter` | 21.09 mm | VERIFIED_FROM_CELL_REFERENCE | 2170 external diameter from `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` |
| `Package m_dextHeight` | 70.02 mm | VERIFIED_FROM_CELL_REFERENCE | 2170 external height from same reference |
| `Package m_dintDiameter` | 20.6274 mm | DERIVED | = 21.09 − 2 × 0.2313 (OD − 2 × can wall). Can wall 0.2313 mm from reference doc. |
| `Package m_dintHeight` | 65.11 mm | VERIFIED_FROM_ABOUT_ENERGY | = negative electrode collector width from `python/params.csv` (jelly-roll active height) |
| `Package m_strName` | `2170` | VERIFIED_FROM_CELL_REFERENCE | Cell format name. |
| `DataSheet m_dDSHeight` | 65.0 mm | **ASSUMED / SUSPICIOUS** | Value not updated from 18650 clone (18650 is also 65 mm). Should be 70.02 mm (can external height) or 65.11 mm (JR height). Label field only — does not drive geometry, but inconsistency with `m_dextHeight = 70.02` is a red flag for a reviewer. |
| `DataSheet m_dDSDiameter` | 21 mm | VERIFIED_FROM_CELL_REFERENCE | Rounded from 21.09 mm. |

---

## Detailed Builder — winding geometry

| Field | Value | Classification | Notes |
|---|---|---|---|
| `m_dJellyrollThickness_mm` | 19.25 mm | **UNKNOWN / WRONG** | This is the jellyroll outer diameter. Value appears to be a carry-over from the source. The correct value should be approximately equal to the can ID (20.6274 mm) for the JR to contact the can. Current value leaves 1.38 mm radial gap. Source of 19.25 mm is not traced. **This is the highest-risk unresolved geometry field.** |
| `m_dMandrelThickness_mm` | 6.0 mm | VERIFIED_FROM_CELL_REFERENCE | Mandrel diameter 6 mm, confirmed from cell teardown/reference. |
| `m_dMandrelWidth_mm` | 6.0 mm | ASSUMED | Set equal to `m_dMandrelThickness_mm`. For a cylindrical mandrel, width = thickness. Not independently confirmed. HE18650 reference does not have this field. |
| `m_bMandrelFlat` | 0 | VERIFIED_FROM_SIEMENS_REFERENCE | 0 = cylindrical mandrel. Correct for 2170 (cylindrical cell). Matches HE18650 reference. |
| `m_dElectrodeOverlapAtStart_mm` | 8.0 mm | ASSUMED | Copied from Simple Builder block (`m_dElectrodeOverlapAtStart = 8`) in the same source TBM. The Detailed Builder occurrence was 0 (a placeholder). The 8 mm value has not been confirmed from About-Energy's electrode design data. |
| `m_dElectrodeOverlapAtEnd_mm` | 20.0 mm | UNKNOWN | Value retained from source TBM. HE18650 reference has ~10 mm. Not confirmed from cell spec. May be wrong. |
| `m_dSepFeedLength_mm` | 0 | COPIED_FROM_KNOWN_GOOD_TEMPLATE | HE18650 reference does not have this field (effectively 0). Our template had 0 in Detailed Builder (10 in Simple Builder). 0 retained. Effect of 0 in 3D mode UNCONFIRMED. |
| `m_dSepTailLength_mm` | 0 | COPIED_FROM_KNOWN_GOOD_TEMPLATE | Same rationale as SepFeedLength. |
| `+Electrode Collector m_dWidth_mm` | 64.11 mm | VERIFIED_FROM_ABOUT_ENERGY | Positive electrode collector width (= axial active height) from About-Energy characterisation data. |
| `-Electrode Collector m_dWidth_mm` | 65.11 mm | VERIFIED_FROM_ABOUT_ENERGY | Negative electrode collector width from About-Energy characterisation data. This is the cell's active jelly-roll height. |

---

## Tab configuration (variant-dependent)

| Field | V1 (tabs-on-std) | V2 (tabs-off-std) | V3 (tabs-on-SF) | V4 (tabs-off-SF) | Classification | Notes |
|---|---|---|---|---|---|---|
| `m_bNegTab` | 1 | 0 | 1 | 0 | TEST VARIANT | Controls presence of negative tab in BDS geometry. |
| `m_bPosTab` | 1 | 0 | 1 | 0 | TEST VARIANT | Controls presence of positive tab in BDS geometry. |
| `m_nNegTabVertOrientation` | 1 (bottom) | 1 (bottom) | 0 (top) | 0 (top) | TEST VARIANT | 0=top, 1=bottom. Same-face target config: 0. |
| `m_nPosTabVertOrientation` | 0 (top) | 0 (top) | 0 (top) | 0 (top) | VERIFIED_FROM_ABOUT_ENERGY | Positive tab is on top — confirmed with Miles 2026-09-03. |

---

## Electrochemical mode flags

| Field | Value | Classification | Notes |
|---|---|---|---|
| `m_bOnly1D` (4 blocks) | 0 (all) | ASSUMED | Set to 0 to allow 3D distributed operation. V3 fix. The HE18650 reference does not have this field (effectively absent = not 1D-only). The HP18650 template has [1,false,0,0]. Whether first-block 0 vs 1 matters is UNCONFIRMED. |
| `m_bSpecifyCapacity` | 0 | ASSUMED | Capacity derived from electrode geometry. If all JR geometry dims were correct for 2170, this would be acceptable. With `m_dJellyrollThickness_mm` still at 19.25 (not yet corrected), the derived capacity may be off. |
| `m_dAhCell` | 0 | ASSUMED | Explicitly zero because `m_bSpecifyCapacity = 0`. Nominal capacity is 5 Ah (from `python/params.csv`). |

---

## Electrochemical tables — RCRTable 3D

| Field | Value | Classification | Notes |
|---|---|---|---|
| `Set[0]_m_dT` | 288.15 K | VERIFIED_FROM_ABOUT_ENERGY | = 15°C. From `python/params.csv` column T_degC. |
| `Set[1]_m_dT` | 298.15 K | VERIFIED_FROM_ABOUT_ENERGY | = 25°C. |
| `Set[2]_m_dT` | 308.15 K | VERIFIED_FROM_ABOUT_ENERGY | = 35°C. |
| `Set[N]_RCR_V_SOC_M` (7 pts) | From params.csv | VERIFIED_FROM_ABOUT_ENERGY | 7 SOC points per temperature set. |
| `Set[N]_RCR_V_Ro_M` (7 pts) | 0.00568–0.00862 Ω | VERIFIED_FROM_ABOUT_ENERGY | R0 (ohmic resistance) from `python/params.csv`. Valid range confirmed by static validator. |
| `Set[N]_RCR_V_Rp_M` / `_V_tau_M` | From params.csv | VERIFIED_FROM_ABOUT_ENERGY | R1, τ1 for RC pair 1. |
| `Set[N]_RCR_V_Rp1_M` / `_V_tau1_M` | From params.csv | VERIFIED_FROM_ABOUT_ENERGY | R2, τ2 for RC pair 2 (if present). |
| OCV equilibrium data | From About-Energy | VERIFIED_FROM_ABOUT_ENERGY | Populated by `translate_tbm_from_openfoam.py`. |

---

## Summary: open / highest-risk fields

Ranked by risk to STAR-CCM+ import or physics correctness:

| # | Field | Issue | Risk level |
|---|---|---|---|
| 1 | `m_dJellyrollThickness_mm = 19.25` | 1.38 mm gap to can ID; JR may not contact can in BDS geometry | HIGH — may cause geometry defect |
| 2 | `m_bOnly1D = 0` in all 4 blocks | Pattern not confirmed against documented Siemens spec; may need first=1 | MEDIUM — awaiting import test |
| 3 | `m_bSpecifyCapacity = 0` | Derived capacity may be off because JR geometry not fully correct | MEDIUM — silent physics error |
| 4 | `m_dElectrodeOverlapAtEnd_mm = 20` | Not confirmed from cell spec; deviates from 18650 reference | LOW-MEDIUM |
| 5 | `DataSheet m_dDSHeight = 65` | Label inconsistency; does not drive geometry | LOW |
| 6 | `m_dElectrodeOverlapAtStart_mm = 8` | Value from Simple Builder; not confirmed from About-Energy | LOW (used in v2+ without blocking error) |
| 7 | `m_dMandrelWidth_mm = 6` | Assumed equal to thickness; HE18650 doesn't have field | LOW |
| 8 | `m_dSepFeedLength_mm = 0` | Matches HE18650 reference but unconfirmed for 3D | LOW |
