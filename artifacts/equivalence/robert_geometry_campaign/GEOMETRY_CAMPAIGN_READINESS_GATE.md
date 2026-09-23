# Geometry Campaign — Campaign Readiness Gate Evaluation

**Package:** ROBERT_GEOMETRY_CAMPAIGN_20260923
**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Status: NOT YET DISPATCHED TO ROBERT**
**Frozen audit version:** ECM_EQUIVALENCE_MASTER_MATRIX.md HEAD 479ef02 (138 requirements)

---

## Gate 1 — Requirement traceability

**PASS.**

All deliverables map to requirement IDs. This is a geometry-characterisation round that establishes operative TBM field controls; each case advances OPEN GEO requirements toward resolution.

| Campaign case | GEO requirement IDs advanced |
|---|---|
| RAD-A (m_dintDiameter probe) | GEO-002 (Can ID), GEO-003 (Can OD), GEO-004 (wall thickness — derived) |
| RAD-B (m_dRepCanX/Y probe) | GEO-003 (Can OD), GEO-004 |
| RAD-C (m_dJellyrollThickness_mm probe) | GEO-001 (JR OD), GEO-022 (JR thermal volume) |
| AX-A (m_dextHeight probe) | GEO-010 (Can axial range), GEO-013 (Can top flush), GEO-014 (Can bottom position) |
| AX-B (SepTail zero) | GEO-009 (JR axial z-range), GEO-016 (no bottom Cap), GEO-021 (no symmetric end-stack) |
| AX-C (SepFeed zero) | GEO-009, GEO-013, GEO-017 (no free void) |
| AX-D (EndOverlap probe) | GEO-009, GEO-017 |
| CEN-A (Mandrel 0.5mm probe) | GEO-005 (full solid JR), GEO-015 (no Mandrel domain) |

---

## Gate 2 — Orphan-requirement scan

**PASS.** No requirement family orphaned. All non-GEO families (TOP, MAT, IFC, BC, SRC, IC, LUMP, ELEC, DIST, STAR, VAL, RUN) are untouched. S0 is parked, not cancelled; all STAR family requirements retain S0 as their resolution path.

---

## Gate 3 — Contradiction audit

**PASS.** No contradiction in C01–C10 affects geometry-only TBM-to-STEP instructions. No heat-source, resistance, or electrical instructions. C04 (F-series): no instruction states zero-clearance is impossible; RAD-C uses a downward perturbation safely below current T06 generated Can ID.

---

## Gate 4 — S0 prerequisite check

**PASS (not needed).** TBM-to-STEP geometry export does not depend on any STAR capability evidence. S0 is parked independently.

---

## Gate 5 — Geometry dimensions and mode-correct configuration

**PASS.**

**5a — Geometry:** All sweep values explicitly labelled in CASE_MATRIX and README. No proven-impossible radial combination present.

Safety assessment (from T06 STEP-confirmed dimensions + perturbation direction — NOT from field-value inequalities):
- RAD-A: m_dJellyrollThickness_mm stays at 17.9; changing m_dintDiameter to 19.0 is safe whether it controls OD (~19mm > current Can ID 18mm) or ID (~19mm > current JR OD 17.881mm).
- RAD-B: JR field unchanged at 17.9; changing m_dRepCanX/Y to 19 does not affect the JR/Can radial relationship.
- RAD-C: m_dJellyrollThickness_mm decreases from 17.9 to 17.5 — moves JR OD downward, away from current Can ID 18.0mm. Safe direction.
- AX-A/B/C/D: no radial field change; current T06 radial geometry preserved.
- CEN-A: Mandrel field reduced; no radial impact. H001 (zero Mandrel non-constructible) is respected: value set to 0.5mm, not zero.

JR OD = Can ID (exact contact) is NOT in this package. Deferred until RAD-A and RAD-C confirm operative field controls.

**5b:** No TBM changes m_dAhCell, m_nRCRParameterSets, transport number, S3 values, or AE data source.

**5c/5d:** Not applicable — no STAR run.

---

## Gate 6 — Robert deliverable completeness

**PASS.**

Robert's only deliverable per case: the exported STEP file (or BDS error text if generation fails). No dimension measurement requested from Robert. Automated post-return B-Rep analysis computes all required geometry quantities.

Quantities we compute automatically after return:
- body names and count
- JR OD, JR inner radius, JR axial range
- Mandrel OD (if present)
- Can inner diameter, Can outer diameter, Can wall thickness, Can axial range
- JR-to-Can top and bottom overhang
- Root/Stem/Washer/Post/EndPlate extents
- pairwise minimum distances (touch graph)
- Boolean overlap volumes

Every GEO requirement ID from Gate 1 is resolved by this automated analysis comparing each returned STEP against the T06 baseline STEP.

---

## Gate 7 — Dependency ordering

**PASS.** No upstream dependencies for TBM-to-STEP export. This package is upstream of all subsequent RAD, GEO-AX, and S0-follow-on packages.

---

## Gate 8 — No stale evidence as a basis

**PASS.** T06 STEP-confirmed dimensions used as baseline (committed audit HEAD 479ef02). TBM_NEXT_EXPERIMENTS.md updated to reflect these measured values (no longer "not yet measured"). No rejected/superseded hypothesis used as design input. H001 (Mandrel-zero constraint) is CONFIRMED/HIGH and respected — zero Mandrel not retested. RMAP-3 treated as an open hypothesis, not a confirmed mapping.

---

## Gate 9 — Requirement coverage continuity

**PASS.** No OPEN or NOT TESTED requirement loses its last resolution path. S0 parked, not cancelled.

---

## Gate 10a — Two-track coverage

**PASS.** No electrical requirements in scope. Geometry-only package.

---

## Gate 10 — Hypothesis ledger consistency

**PASS.**

Pre-dispatch expected outcomes:

| Hypothesis | Expected outcome | Revision trigger |
|---|---|---|
| RMAP-3: m_dintDiameter → radial geometry (RAD-A) | Most likely: Can ID unchanged (inoperative; Can ID tracks JR OD). Also possible: Can ID or Can OD shifts. Both outcomes actionable. | Update DOF matrix and RMAP-3 on return |
| RMAP-2: m_dRepCanX/Y → Can OD (RAD-B) | Can OD shifts toward 19mm per August evidence. Null result also informative. | Update GEO-003 and RMAP-2 on return |
| RMAP-1: m_dJellyrollThickness_mm → JR OD, T06 class (RAD-C) | JR OD shifts proportionally from 17.881 toward ~17.5mm. | Update GEO-001 on return |
| AX package / AXIAL-001/009 | T06 saturation insensitive to separator fields (AX-B/C/D); Can height responsive to m_dextHeight (AX-A). | Refine AXIAL-009 explanation on return |
| Mandrel operativity / H001 (CEN-A) | Mandrel OD reduces proportionally (field operative). Zero non-constructible per H001 — not retested. | Update GEO-005/015 and Mandrel DOF on return |

---

## Summary

All 10 gate points: **PASS**.

GEO IDs addressed: GEO-001, GEO-002, GEO-003, GEO-004, GEO-005, GEO-009, GEO-010, GEO-013, GEO-014, GEO-015, GEO-016, GEO-017, GEO-021, GEO-022 (14 requirements — characterisation-level evidence; production satisfaction pending confirmed field controls).

Robert manual measurements requested: **NONE**. All geometry analysis is automated post-return.

**Package is ready for dispatch when this sentence is removed and replaced with: "Dispatched: [date]."**
