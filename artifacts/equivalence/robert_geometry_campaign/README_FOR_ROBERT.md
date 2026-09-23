# Geometry Campaign — Instructions for Robert

**Date:** 2026-09-23
**Package:** ROBERT_GEOMETRY_CAMPAIGN_20260923
**Type:** TBM-to-STEP conversion only — no STAR import, no physics, no .sim files.

---

## What this package is

This is a pure geometry characterization round. Eight TBM files (derived from the same T06 baseline used in the S0 package) each vary one or two geometric parameters. For each TBM, you open it in BDS, let BDS compute, export the STEP, and measure the key dimensions listed below. No STAR work is needed.

**Do not use the S0 package alongside this one. They are independent.**

---

## What you need for each TBM

For each of the 8 TBM files in `input/`:

1. Open the TBM in BDS (Battery Design Studio).
2. Let BDS recompute the cell geometry completely.
3. Export to STEP (3D CAD file).
4. Measure the following quantities from the STEP (use CAD inspection tools — calipers, bounding box, or equivalent):

   **Radial measurements:**
   - JR OD (Jellyroll outer diameter, mm)
   - Mandrel OD (if body is present, mm; write "ABSENT" if no Mandrel body)
   - Can inner diameter (smallest internal diameter of the Can body, mm)
   - Can outer diameter (largest external diameter of the Can body, mm)

   **Axial measurements (from the full STEP assembly):**
   - Can total height (mm)
   - JR total height (mm)
   - Distance from JR top face to Can top face (mm; positive = Can extends above JR)
   - Distance from JR bottom face to Can bottom face (mm; positive = Can extends below JR)

5. Record the body list: list every solid body name that appears in the STEP and the number of bodies.

6. Note any BDS errors or warnings during generation.

**Return format:** Use the ROBERT_RETURN_TEMPLATE.md. One section per case.

---

## The 8 cases

### RADIAL family

**RAD-A — Can ID field probe** (`GC_RAD_A_can_id_probe.tbm`)
One change from T06 baseline: `Package m_dintDiameter` changed from 20.9 mm → 19.0 mm. All other fields identical to T06.
*Why:* Tests whether m_dintDiameter is the operative Can-ID control field.

**RAD-B — Can OD field probe** (`GC_RAD_B_can_od_probe.tbm`)
One change from T06 baseline: `Package m_dextDiameter` changed from 21.0 mm → 22.0 mm. All other fields identical to T06.
*Why:* Tests whether m_dextDiameter is the operative Can-OD control field.

**RAD-C — JR OD field probe** (`GC_RAD_C_jr_od_probe.tbm`)
One change from T06 baseline: `m_dJellyrollThickness_mm` changed from 17.9 mm → 19.0 mm. All other fields identical to T06.
*Why:* Confirms that m_dJellyrollThickness_mm controls JR OD in the T06 geometry class (previously confirmed in a different cell class; this test verifies transfer).

### AXIAL / END family

**AX-A — Can height probe** (`GC_AX_A_can_height_probe.tbm`)
Two changes from T06: `Package m_dextHeight` 70 → 75 mm; `Package m_dintHeight` 65.11 → 70 mm.
*Why:* Tests whether Package height fields control the Can axial envelope.

**AX-B — Separator tail zero** (`GC_AX_B_sep_tail_zero.tbm`)
One change from T06: `m_dSepTailLength_mm` 85 → 0 mm. Feed length unchanged (10 mm).
*Why:* Tests whether the separator tail length controls the end-stack geometry at one end.

**AX-C — Separator feed zero** (`GC_AX_C_sep_feed_zero.tbm`)
One change from T06: `m_dSepFeedLength_mm` 10 → 0 mm. Tail length unchanged (85 mm).
*Why:* Isolates the separator feed length from the tail length (AX-B). Compare the two cases.

**AX-D — Electrode end-overlap probe** (`GC_AX_D_end_overlap_probe.tbm`)
One change from T06: `m_dElectrodeOverlapAtEnd_mm` 40 → 80 mm. All other fields identical to T06.
*Why:* Tests whether increasing electrode overlap at the end extends the end-stack geometry.

### CENTRAL family

**CEN-A — Mandrel zero probe** (`GC_CEN_A_mandrel_zero.tbm`)
One change from T06: `m_dMandrelThickness_mm` 6 → 0 mm. All other fields identical to T06.
*Why:* Tests whether setting Mandrel thickness to zero removes the Mandrel body and produces a solid full-radius JR.

---

## TBM file checksums

| Case | Filename | SHA-256 |
|---|---|---|
| T06 baseline (reference, unchanged) | T06_TARGET_AXIAL_SURPLUS_2p00.tbm | `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71` |
| RAD-A | GC_RAD_A_can_id_probe.tbm | `05db85fc8c27856044d16429dfa7b659656fd250bd190106e0cfb6911ad8deaa` |
| RAD-B | GC_RAD_B_can_od_probe.tbm | `981191e46d8c0c967abb405ece2583e2097be2af739d89953b1da97072ab873c` |
| RAD-C | GC_RAD_C_jr_od_probe.tbm | `c53c7e4b9d341f59bc3fc816a612244900bb917a4708e25d804654f7a1b4aa91` |
| AX-A | GC_AX_A_can_height_probe.tbm | `8842da406354c96d844b5c79e6f78ef3584e5e239f6bdaefc80fc959b27b2533` |
| AX-B | GC_AX_B_sep_tail_zero.tbm | `b535e1cd9603b9400516a93ba39addffa21e8e0822bfd58c3030d4084554f203` |
| AX-C | GC_AX_C_sep_feed_zero.tbm | `32143c9579f08b3f26db4c3cd445a80d5787702cfc69bddf9ee947df7eb99f08` |
| AX-D | GC_AX_D_end_overlap_probe.tbm | `a6e9ed1a8f0e24b752c911a9be3f9536250bd486ece00adcb1f84ffa61cdfd3e` |
| CEN-A | GC_CEN_A_mandrel_zero.tbm | `8e08c29a47bffece92f1ac57708d0840bd50c0485dab69a21fa3855349da7cdf` |

Verify each file with `sha256sum` or equivalent before starting.

---

## Known BDS generation constraint

Prior testing established that BDS fails to generate a STEP when `m_dJellyrollThickness_mm` ≥ `Package m_dintDiameter` (the JR OD meets or exceeds the Can ID). BDS displays: "Jellyroll outer diameter is greater than Can inner diameter. Can inner diameter set to JR outer diameter." followed by "Can Thickness is -ve". All 8 TBMs in this campaign use `m_dJellyrollThickness_mm` < `Package m_dintDiameter` and are expected to generate without this error. If any TBM does trigger this error, report it in the return template under "BDS error message."

## What NOT to do

- Do NOT import any of these TBMs into STAR-CCM+.
- Do NOT open or modify the S0 package (ROBERT_STAR_S0_QUALIFICATION).
- Do NOT attempt to measure dimensions from the BDS UI report fields — measure from the exported STEP geometry directly.
- Do NOT calculate any dimension manually from formulas — report STEP-measured values.
- Do NOT attach .sim files.

---

## ECM Campaign Readiness Gate — Quick Reference

```
ECM Campaign Readiness Gate — package: GEOMETRY_CAMPAIGN — date: 2026-09-23

[x] Gate 1: GEO-001, GEO-002, GEO-003, GEO-005, GEO-009, GEO-010, GEO-013, GEO-014, GEO-015, GEO-016, GEO-017, GEO-021
[x] Gate 2: No requirement family orphaned; all GEO reqs still have resolution paths; S0 parked independently
[x] Gate 3: No contradiction in C01-C10 affects geometry-only instructions
[x] Gate 4: S0 prerequisite not needed — geometry-only round; TBM changes do not depend on S0 STAR output
[x] Gate 5a: All sweep values explicitly labelled; no proven-impossible radial combination; JR OD = Can ID exact-contact NOT in this package (contingent on RAD-A/C results)
[x] Gate 5b: Common mode-independent params not changed by any TBM in this package
[x] Gate 5c: No STAR physics in this package; IET/Thermal settings not relevant
[x] Gate 5d: Not a lumped-track package
[x] Gate 6: All 8 required dimension tables explicitly listed; body list required for each case
[x] Gate 7: No upstream dependencies for geometry-only STEP measurements
[x] Gate 8: No stale/superseded claim used; T06 STEP audit results used as baseline (CONFIRMED provenance)
[x] Gate 9: All OPEN GEO requirements retain resolution paths; S0 is parked, not cancelled
[x] Gate 10a: No electrical reqs in scope
[x] Gate 10: Pre-dispatch expected outcomes in CASE_MATRIX.md

Blockers: none
```

---

**Status: NOT YET DISPATCHED TO ROBERT**
