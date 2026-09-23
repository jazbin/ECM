# Geometry Campaign — Case Matrix

**Date:** 2026-09-23
**Purpose:** Identify the best achievable TBM geometry relative to the OpenFOAM thermal operator target before any STAR physics work begins.
**Method:** TBM-to-STEP export only. Robert opens each TBM in BDS and exports a STEP file (or reports failure). No STAR import. No manual dimension measurement. Post-return B-Rep analysis is automated on our side.
**Baseline:** T06_TARGET_AXIAL_SURPLUS_2p00.tbm. SHA-256: 433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71

---

## T06 baseline — known STEP-confirmed dimensions

| Quantity | T06 value (STEP-confirmed) | OF target | Gap |
|---|---|---|---|
| JR OD | 17.880992 mm | 20.6274 mm | −2.746 mm |
| Can ID | 18.000000 mm | 20.6274 mm | −2.627 mm |
| Can OD | ~20.90 mm | 21.09 mm | ~−0.19 mm |
| JR↔Can radial gap | 0.059504 mm | 0 mm | +0.059504 mm |
| Mandrel OD | ~6 mm | 0 (none) | +~6 mm |
| Can axial height | ~70 mm | 65.34 mm | +~4.7 mm |
| JR height | 65.11 mm | 65.11 mm | 0 (SATISFIED) |
| JR-to-Can-top | ~2.445 mm | 0 mm | +~2.445 mm |
| JR-to-Can-bottom | ~2.445 mm | 0.231 mm | +~2.214 mm |

Source: `docs/equivalence/T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`; `tbm_validation/TBM_GEOMETRY_DOF_MATRIX.md`.

---

## Controlling TBM fields — evidence status at dispatch

| Field | T06 value | Candidate geometry role | Status |
|---|---|---|---|
| `m_dJellyrollThickness_mm` | 17.9 | JR OD | CONFIRMED August class; T06 transfer OPEN |
| `Package m_dintDiameter` | 20.9 | Unknown — either Can ID or Can OD or neither | OPEN/ambiguous |
| `m_dRepCanXDim` / `m_dRepCanYDim` | 18 / 18 | Possibly Can OD | SUPPORTED/high (August); T06 class OPEN |
| `m_dMandrelThickness_mm` | 6.0 | Mandrel OD | OPEN; zero confirmed non-constructible (H001) |
| `Package m_dextHeight` | 70.0 | Can axial envelope | OPEN |
| `m_dSepTailLength_mm` | 85 | Axial end-stack | OPEN |
| `m_dSepFeedLength_mm` | 10 | Axial end-stack | OPEN |
| `m_dElectrodeOverlapAtEnd_mm` | 40 | End-stack extent | OPEN |

---

## Post-return analysis (automated — NOT from Robert)

For all successful STEP files returned, we compute via exact B-Rep tools (`tools/audit_bds_openfoam_overlap.py` and equivalent):

- body names and count
- JR OD, JR ID (inner void radius if any), JR axial min/max
- Mandrel OD (if body present), Mandrel axial extents
- Can inner diameter, Can outer diameter, Can wall thickness, Can axial min/max
- top/bottom overhang (Can max − JR max; JR min − Can min)
- Root/Stem/Washer/Post/EndPlate axial extents and radial bounds
- pairwise min distances (touch graph)
- Boolean overlap volumes for Can↔EndPlate

Robert does not measure any dimension.

---

## Case matrix

### RADIAL family — 3 TBMs

| Case | TBM filename | Field(s) changed | From | To | GEO req. | Question under test |
|---|---|---|---|---|---|---|
| RAD-A | GC_RAD_A_can_id_probe.tbm | `Package m_dintDiameter` | 20.9 | 19.0 | GEO-002, GEO-003 | Which generated radial quantity (Can ID, Can OD, or neither) responds to m_dintDiameter? |
| RAD-B | GC_RAD_B_can_rep_xy_probe.tbm | `m_dRepCanXDim`, `m_dRepCanYDim` | 18 / 18 | 19 / 19 | GEO-003 | Which generated radial quantity (Can OD, Can ID, or neither) responds to m_dRepCanX/Y? |
| RAD-C | GC_RAD_C_jr_od_probe.tbm | `m_dJellyrollThickness_mm` | 17.9 | 17.5 | GEO-001 | Does JR OD respond proportionally to m_dJellyrollThickness_mm on the T06 geometry class? |

**RAD-A safety:** m_dJellyrollThickness_mm stays at 17.9; current T06 generated Can ID = 18.000mm. Changing m_dintDiameter to 19.0 is safe in either direction of mapping: if it controls OD (20.9→19mm), OD remains above current Can ID; if it controls ID (20.9→19mm), ID still exceeds current JR OD 17.881mm.

**RAD-B safety:** m_dJellyrollThickness_mm stays at 17.9; changing m_dRepCanXDim/YDim 18→19 is safe in both possible outcomes (OD or ID change).

**RAD-C safety:** Decreasing m_dJellyrollThickness_mm from 17.9 to 17.5 moves JR OD downward, away from Can ID. No geometry conflict possible.

Note: safety assessed from T06 generated STEP dimensions and direction of perturbation — NOT from field-value inequalities.

### AXIAL/END family — 4 TBMs

| Case | TBM filename | Field changed | From | To | GEO req. | Question under test |
|---|---|---|---|---|---|---|
| AX-A | GC_AX_A_ext_height_probe.tbm | `Package m_dextHeight` | 70 | 75 | GEO-010, GEO-013, GEO-014 | What generated axial/end geometry changes when package external height is increased? Does Can envelope change? Does JR placement shift? |
| AX-B | GC_AX_B_sep_tail_zero.tbm | `m_dSepTailLength_mm` | 85 | 0 | GEO-009, GEO-016, GEO-021 | What generated axial/end geometry changes when separator tail length is set to zero? |
| AX-C | GC_AX_C_sep_feed_zero.tbm | `m_dSepFeedLength_mm` | 10 | 0 | GEO-009, GEO-013, GEO-021 | What generated axial/end geometry changes when separator feed length is set to zero? (Isolated from AX-B.) |
| AX-D | GC_AX_D_end_overlap_probe.tbm | `m_dElectrodeOverlapAtEnd_mm` | 40 | 80 | GEO-009, GEO-017 | What generated axial/end geometry changes when electrode end-overlap is increased to 80 mm? |

**AX-A isolation:** Only m_dextHeight changes; m_dintHeight remains at 65.11mm. This isolates the external height field from the internal height field. Automated post-return comparison directly answers whether the Can envelope responds to m_dextHeight alone.

**AX-B and AX-C:** Different fields isolated independently. Do not assume tail controls one end and feed the other — automated B-Rep comparison determines which body/end responds.

**AX-D:** Do not assume that larger overlap extends the stack; T06 saturation evidence (AXIAL-009) makes this possible but not certain. Automated comparison determines actual change.

### CENTRAL family — 1 TBM

| Case | TBM filename | Field changed | From | To | GEO req. | Question under test |
|---|---|---|---|---|---|---|
| CEN-A | GC_CEN_A_mandrel_probe.tbm | `m_dMandrelThickness_mm` | 6.0 | 0.5 | GEO-005, GEO-015 | Does m_dMandrelThickness_mm control generated Mandrel OD on the T06 class? Does the JR inner void radius respond proportionally? |

**CEN-A constraint:** Zero Mandrel is NOT retested. H001 is CONFIRMED/HIGH: STAR/CreateFromTbm rejects zero or negative Mandrel thickness with "Mandrel thickness must be positive." Zero Mandrel is non-constructible under this constraint. The campaign tests whether the smallest practical positive value (0.5mm) is achievable and whether the field is operative at all.

Zero-Mandrel record: non-constructible under H001. Not retested in this campaign.

---

## Redundancy evaluation

- RAD-A and RAD-B: both test the Can OD/ID question from different field angles. Can OD, Can ID, and JR OD must all be compared across both cases to resolve the ambiguity in the current evidence.
- RAD-C is independent: tests JR OD control only.
- AX-A, AX-B, AX-C, AX-D: all test different fields or different aspects of axial geometry. AX-B and AX-C are NOT interchangeable — they isolate different fields.
- CEN-A: single test covers the Mandrel operativity question within the H001 constraint.

No case is redundant. **Total: 8 TBMs.**

---

## Pre-dispatch expected outcomes

| Case | Most likely result | Alternative | Both outcomes actionable? |
|---|---|---|---|
| RAD-A | Can ID unchanged at ~18mm (m_dintDiameter not Can ID driver; Can ID tracks JR OD) | Can ID shifts toward 19mm (m_dintDiameter operative) | YES |
| RAD-B | Can OD changes (m_dRepCanX/Y operative per August RMAP-2) | No change (REPORT block regenerated at import; another field drives Can OD) | YES |
| RAD-C | JR OD shifts to ~17.5mm proportionally | JR OD unchanged (field not operative in T06 class) | YES |
| AX-A | Can height changes from ~70mm toward ~75mm | No change (envelope fixed by another mechanism) | YES |
| AX-B | No geometry change (T06 saturation robust to tail) | End-stack changes at tail end | YES |
| AX-C | No geometry change (consistent with AX-B; both saturation-insensitive) | End-stack changes at feed end | YES |
| AX-D | No end-stack change (saturation is envelope-limited, not overlap-limited) | End-stack extent increases | YES — distinguishes AXIAL-009 competing explanations |
| CEN-A | Mandrel OD reduces proportionally (field operative); JR inner radius reduces | Mandrel OD unchanged (field inoperative); body absent or error | YES |
