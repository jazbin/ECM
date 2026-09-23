# ECM Experiment Coverage Matrix

**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Purpose:** Map every historical and planned experiment to the requirements in `ECM_EQUIVALENCE_MASTER_MATRIX.md`. Identify requirement families with zero experiment coverage (orphan requirements) and experiments with no corresponding requirement (orphan experiments).

Columns: `Experiment | Type | Status | Req IDs addressed | Req IDs it CANNOT address | Output evidence | Dependencies | Still needed?`

---

## Historical experiments (completed — Robert-returned evidence)

| Experiment | Type | Status | Req IDs addressed | Req IDs it CANNOT address (notable) | Output evidence | Dependencies | Still needed? |
|---|---|---|---|---|---|---|---|
| **D00 — TBM baseline import** | STAR import | Complete | STAR-001 (13 Regions confirmed) | All geometry/material/interface/electrical reqs | 13 Regions confirmed from prior STAR work | T06 TBM generated | No |
| **R001–R004 — TBM field/runtime identification, H/T/F initial series** | TBM generation + STAR | Complete | ELEC-003 (m_bOnly1D=0, R004); RUN-007; ELEC-004/RUN-005 (partial) | Geometry, interface, material, BC, SRC, DIST, VAL | `TBM_HYPOTHESIS_LEDGER.md`; R004 warning cleared | TBM generation | No |
| **R005 — Transport number, m_dS3 verification** | TBM parameter check | Complete | RUN-008 (Transport=0), RUN-009 (m_dS3 values) | Geometry, interface, material, BC, SRC, DIST, VAL | R005 confirmed | — | No |
| **August characterization — JR OD / Can OD radial correlation** | TBM generation + STAR | Complete | GEO-001 (partial), GEO-003 (partial), RMAP-1 (CONFIRMED), RMAP-2 (SUPPORTED) | Can ID (RMAP-3 still OPEN), axial, interface, material, BC, IC, SRC, DIST, VAL | RMAP-1 confirmed isolated; RMAP-2 correlated; JR OD vs m_dJellyrollThickness_mm strongly established | TBM field exploration | No; but provides priors for RAD-A/B/C |
| **H01–H08, H13 — Electrode surplus variation (saturated plateau)** | TBM generation + STAR | Complete; plateau | E004 (pass/fail rule); ELEC tab root/stem surplus PASS threshold (H007 hypothesis) | GEO-001/002/003/004, GEO-006/007, axial, interface, material, BC, IC, SRC, DIST, VAL | `TBM_HYPOTHESIS_LEDGER.md` H007: SUPPORTED HIGH; tab surplus rule identified | E004 blocker context | No (plateau confirmed) |
| **H11, H12 — Both-side surplus variation (changed geometry)** | TBM generation + STAR | Complete | H-series geometry plateau characterization; confirms coupled surplus construction | Same as H01–H08 | Both-side changes alter geometry; independent per-polarity pure extrusion refuted | — | No |
| **T01, T04–T08 — JR height + surplus saturation (T06 baseline freeze)** | TBM generation + STAR | Complete; T06 frozen | GEO-008 (JR height SATISFIED); T06 baseline fixed | GEO-001..007, GEO-009..024, all other families | STEP audit: JR height 65.11mm; T06/T07/T08 identical geometry | — | No; T06 is frozen baseline |
| **F01–F09 — F-series (JR OD at OF target, Can OD not updated)** | TBM generation + STAR | Complete; all FAIL | GEO-001 (partial — RMAP-1 transfer to T06-class geometry confirmed possible); H008a, H008b | Can ID (RMAP-3 still OPEN); JR OD = Can ID exact-contact never tested | F-series FAIL: "Can Thickness -ve"; JR OD > Can OD confirmed failure mode; zero-clearance OPEN | September Robert return | RAD-A/B/C/D needed to redo with corrected Can OD |

---

## S0 — STAR Capability Gate (planned, not yet run)

| Experiment | Type | Status | Req IDs addressed | Notable gaps | Output evidence needed | Dependencies | Still needed? |
|---|---|---|---|---|---|---|---|
| **S0-R0 — T06 import, save baseline .sim** | STAR import | NOT RUN | RUN-004 (STAR version), STAR-001 (re-confirm), GEO-001/003/007 (Region geometry visible) | Material properties, interface types, BCs, electrical, anything requiring solver run | T06_S0_baseline.sim; STAR version string | T06 TBM package | YES — first step |
| **S0-A — Region volume reports + centerline section** | STAR post-import | NOT RUN | GEO-022/023/024 (if volumes reported); GEO-020 (Can-EndPlate overlap resolution); GEO-015/019 (Region existence), STAR-008/009 | Interface types/areas, material properties, BCs, electrical reqs; GEO-001..007 individual dimensions | Per-Region volume table; screenshot | S0-R0 | YES |
| **S0-B — Interface tree inspection (14 Region pairs)** | STAR post-import | NOT RUN | TOP-001 (radial gap bridged?); TOP-003/005 (Root contacts); TOP-007 (Can-Cap); STAR-003/007/010/011 | Interface resistances (not settable until tested); material values; BCs; electrical; DIST; VAL | Interface tree: exists/type for each of 14 pairs; quantitative area for Root↔JR pairs (CRITICAL) | S0-R0 | YES — must request AREA for Root-JR pairs, not just existence |
| **S0-C — +Tab Stem thermal material independence (k→0.01 test)** | STAR material assignment | NOT RUN | STAR-002/004/005/014; MAT-001..014; ELEC-001/002 (partial); GEO-005/015 (Mandrel assignability) | Interface resistances; BCs; IC; SRC; DIST; VAL; geometry dimensions | +Tab Stem material change: retained electrical role? error? | S0-R0, S0-B | YES |
| **S0-D — Bottom thermal path suppression (4 mechanisms D1–D4)** | STAR thermal model | NOT RUN | GEO-016/017/021; TOP-003/004/012/014; IFC-002 (resistance hookable?); STAR-006/013; RUN-001/002 | Dimensions; material values; BC values; SRC; ELEC/DIST output metrics; VAL output | Suppression mechanism result for each D1–D4; −Tab electrical role intact? | S0-C | YES |

---

## RAD — Radial Dimension Campaign (planned, not yet run)

| Experiment | Type | Status | Req IDs addressed | Notable gaps | Output evidence needed | Dependencies | Still needed? |
|---|---|---|---|---|---|---|---|
| **RAD-A — m_dintDiameter 20.9→20.5mm; measure Can ID/OD/JR OD** | TBM parameter + STAR | NOT RUN | GEO-002 (Can ID OPEN); RMAP-3 (Can ID operative control); TOP-001/009 (if gap closes) | Axial, interface type/area, material, BC, SRC, IC, DIST, VAL, electrical semantics | Generated Can ID value vs input; generated Can OD; generated JR OD | T06 geometry class; existing F-series failure analysis | YES — can run parallel to S0 |
| **RAD-B — m_dRepCanXDim/YDim 18→19mm; measure Can OD** | TBM parameter + STAR | NOT RUN | GEO-003 (Can OD); RMAP-2 confirmation | All other reqs | Generated Can OD | T06 geometry class | YES — low priority (D classification); fold into RAD package |
| **RAD-C — m_dJellyrollThickness_mm 17.9→17.5mm; measure JR OD** | TBM parameter + STAR | NOT RUN | GEO-001 (JR OD DOF confirmation in T06-class geometry); RMAP-1 in T06 class | Axial, interface, material, BC, SRC, IC, DIST, VAL, electrical semantics | Generated JR OD value vs input | T06 geometry class | YES — confirm RMAP-1 holds for T06 JR height |
| **RAD-D1 — Positive-clearance production (JR OD≈20.50mm, Can ID=20.6274mm)** | TBM geometry | NOT RUN | GEO-001/002/003/004/007; TOP-001/002/009; GEO-022/023 | Axial, interface area, material, BC, SRC, IC, DIST, VAL, STAR-007 gap tolerance | STEP with production-close radial geometry; Can ID > JR OD confirmed | RAD-A, RAD-C (confirmed DOF control) | YES — after RAD-A/C |
| **RAD-D2 — Exact contact (generated JR OD = generated Can ID = 20.6274mm)** | TBM geometry | NOT RUN | GEO-007 (zero-gap contact); TOP-009; H004-3 (OPEN LOW hypothesis) | Interface area/type (depends on S0-B); axial, material, BC, SRC, IC, DIST, VAL | Successful or failed STAR TBM build with exact-contact geometry | RAD-A (Can ID DOF); RAD-C (JR OD DOF); RAD-D1 (positive-clearance baseline) | YES — tests H004-3; needed if S0-B shows STAR cannot bridge gap |

---

## Tests A/B/C/D — Operator Equivalence Tests (planned, not yet run; require S0 pass + geometry corrections)

| Experiment | Type | Status | Req IDs addressed | Notable gaps | Output evidence needed | Dependencies | Still needed? |
|---|---|---|---|---|---|---|---|
| **Test A — Thermal baseline (fixed heat source, no ECM)** | STAR thermal run | NOT RUN | MAT-001..012; BC-001..005; SRC-001/002/003/006/007; IC-001; IFC-001..006; VAL-004..015; TOP-010; STAR-004/012 | ELEC/DIST/RUN-001 (no ECM yet); VAL-001/002/016 (electrical) | T(x,t), T_regions(t), E_stored(t), Q_ext(t), V(t) n/a; 9 probe time series | S0 pass; geometry corrections (GEO-001/002); material mapping from BDS_TO_OPENFOAM | YES — primary thermal equivalence test |
| **Test B — Electrical integration (ECM on, verify distributed activation)** | STAR ECM run | NOT RUN | ELEC-001/002/006/007/008/009/010/012; RUN-001/002/003/006 | DIST (not yet; spatial gradients needed for Test C); VAL-016 | V(t), SOC(t); no solver errors; native STAR model confirmed | Test A pass; correct TBM radial geometry | YES |
| **Test C — Distributed semantics (spatial SOC/T coupling)** | STAR ECM + thermal | NOT RUN | DIST-001..005; VAL-016; ELEC-001..010 | All geometry reqs must already be met | T(x_A,t) ≠ T(x_B,t) → SOC(x_A,t) ≠ SOC(x_B,t); q(x_A,t) ≠ q(x_B,t) | Test B pass; spatial T gradient must exist | YES |
| **Test D — Full coupled comparison with OF reference** | STAR ECM + thermal | NOT RUN | VAL-001..016; ELEC-009/010; SRC-004/005; all remaining open reqs | Must resolve SRC-008 (f_cap conflict) before test design | V(t) vs OF; SOC(t) vs OF; T_JR_mean vs OF; final energy balance | Test C pass; SRC-008 resolved; VAL-017 clean reference | YES |

---

## Axial / geometry tests (planned; gated on S0 + RAD completion)

| Experiment | Type | Status | Req IDs addressed | Notable gaps | Output evidence needed | Dependencies | Still needed? |
|---|---|---|---|---|---|---|---|
| **GEO-AX — Axial envelope and end-stack topology correction** | TBM geometry | NOT RUN | GEO-009/010/011/012/013/014; GEO-016/017/021; TOP-003/004/005/006/012/014; IFC-002; VAL-013 | Material properties (separate); BCs, SRC, IC, DIST, electrical | Corrected axial STEP: JR asymmetric placement, Can flush with JR top, Can-bottom disc | S0-D result (end-stack suppression route); RAD-A/C (radial corrections first) | YES — gated on S0-D |

---

## Orphan requirements (no current planned experiment addresses them)

| Requirement ID | Requirement summary | Why orphaned | Suggested new experiment or action |
|---|---|---|---|
| IFC-002 | Explicit bottom interface resistance R=6.015×10⁻⁷ m²K/W | GEO-AX provides geometry; S0-D tests suppression mechanism; but explicit resistance value verification in STAR is not explicitly in any test | Add to S0-D instructions: verify resistance settable on Can-JR bottom contact |
| IFC-005 | No radiation on internal interfaces | No current test checks this | Add to Test A setup checklist |
| BC-003 | No fixed-T BC on external surface | Implicit in Test A but not explicitly stated as a check | Add explicit BC verification step to Test A instructions |
| BC-004 | No radiation BC on external surface | Same as BC-003 | Add to Test A |
| SRC-008 | f_cap = 0 (executable) vs f_cap = 0.034 (documented) contradiction | Contradiction not resolved; Test D design depends on which is authoritative; no current task resolves it | Inspect OF fvOptions source for jellyRoll_rotated and cap_rotated; verify 0% Cap assignment; update `OPENFOAM_THERMAL_OPERATOR_INVENTORY.md` |
| MAT-006 | JR k tensor must be anisotropic cylindrical | Mentioned in Test A material check but STAR capability is NOT explicitly tested in S0-C | Add explicit cylindrical-anisotropic k capability check to S0-C instructions |
| MAT-012 | Cap k tensor must be anisotropic cylindrical | Same as MAT-006 | Same action |
| GEO-AX/IFC-002 combined | Can bottom disc + resistance layer | GEO-AX is planned but its dependence on S0-D result and the specific resistance application mechanism in STAR are not in any current Robert instructions | Prepare GEO-AX package contingent on S0-D outcome |
| VAL-013 | Top-end ≠ bottom-end T asymmetry | No experiment explicitly verifies this observable; it is a consequence of axial geometry corrections | Fold into Test A acceptance criteria post-GEO-AX |
| STAR-012 | 3-way piecewise material assignment within Can body | Test A instructs this; S0-A volumes give input; but the capability is labeled "unknown" and has no separate S0-level check | Add to S0-A: note if STAR produces sub-regions within Can body |

---

## Orphan experiments (none found)

Every historical and planned experiment maps to at least one requirement. No experiment is without justification.

---

## Coverage summary by requirement family

| Family | Total reqs | Covered by ≥ 1 experiment | Orphaned (zero coverage) | Notes |
|---|---|---|---|---|
| GEO | 24 | 20 | 4 (GEO-009,014 partial; GEO-011,012 only via gated GEO-AX) | Axial tests gated; all radial covered by RAD |
| TOP | 15 | 13 | 2 (TOP-008 partial; TOP-015 no dedicated check beyond S0-A) | S0-B provides most topology evidence |
| MAT | 14 | 12 | 2 (MAT-006 anisotropic k capability; MAT-012 anisotropic k for Cap) | Need explicit STAR capability check in S0-C |
| IFC | 6 | 4 | 2 (IFC-005 radiation check; IFC-002 explicit resistance value) | Need additions to S0-D and Test A |
| BC | 5 | 3 | 2 (BC-003 no fixed-T; BC-004 no radiation) | Need addition to Test A setup checklist |
| SRC | 8 | 6 | 1 (SRC-008 f_cap conflict unresolved — no test yet) | Must resolve before Test D |
| IC | 1 | 1 | 0 | Test A sets IC |
| ELEC | 12 | 9 | 3 (ELEC-007/008/009 set during Test B/C/D but not in S0 scope) | Acceptable; gated correctly |
| DIST | 5 | 5 | 0 | Test C covers all |
| STAR | 14 | 12 | 2 (STAR-012 3-way Can split; STAR-013 resistance on face) | Add to S0-A and S0-D |
| VAL | 17 | 15 | 2 (VAL-013 asymmetry observable; IFC-005/BC checks in Test A) | Fold into Test A acceptance |
| RUN | 9 | 8 | 1 (RUN-003 time step matching) | Add to Test A/D setup |
