# Geometry Campaign — Instructions for Robert

**Date:** 2026-09-23
**Package:** ROBERT_GEOMETRY_CAMPAIGN_20260923
**Type:** TBM-to-STEP export only — no STAR import, no physics, no manual dimension measurement.

---

## Your workflow

For each TBM file in `input/`:

1. Verify the file's SHA-256 matches the table at the end of this document.
2. Open the TBM in BDS (Battery Design Studio).
3. Let BDS recompute the cell geometry completely.
4. **If BDS generates successfully:** export the STEP file. Name it with the same base name as the TBM (e.g. `GC_RAD_A_can_id_probe.step`). Return all STEP files.
5. **If BDS reports an error:** record the exact error text (and screenshot if practical). Do not attempt to fix it — just report it.

**That is all.** Do not take any dimension measurements. Do not count bodies. Do not open the STEP in another CAD tool to inspect geometry. Return the STEP files and the error log. We run automated B-Rep analysis on our side after return.

---

## What we compute after you return the STEPs

We will compute the following automatically from every returned STEP:

- body names and count
- JR OD, JR inner radius, JR axial range
- Mandrel OD (if body present)
- Can inner diameter, Can outer diameter, Can wall thickness, Can axial range
- JR-to-Can top and bottom overhang
- Root / Stem / Washer / Post / EndPlate extents
- all pairwise minimum distances (touch graph)
- Boolean overlap volumes

You do not need to measure or report any of these.

---

## Known BDS construction constraint

Prior testing confirmed that BDS cannot build a geometry when the Jellyroll OD meets or exceeds the Can ID. Error: "Jellyroll outer diameter is greater than Can inner diameter" followed by "Can Thickness is -ve." All 8 TBMs in this package use a downward or laterally safe Jellyroll input and are expected to generate without this error. If any TBM does trigger it, report the exact error text.

---

## The 8 cases

### RADIAL family

**RAD-A** (`GC_RAD_A_can_id_probe.tbm`)
Single change from T06 baseline: `Package m_dintDiameter` 20.9 mm → 19.0 mm.

**RAD-B** (`GC_RAD_B_can_rep_xy_probe.tbm`)
Two changes from T06 baseline: `m_dRepCanXDim` 18 mm → 19 mm; `m_dRepCanYDim` 18 mm → 19 mm. Both changed together (circular cross-section requires X = Y).

**RAD-C** (`GC_RAD_C_jr_od_probe.tbm`)
Single change from T06 baseline: `m_dJellyrollThickness_mm` 17.9 mm → 17.5 mm.

### AXIAL / END family

**AX-A** (`GC_AX_A_ext_height_probe.tbm`)
Single change: `Package m_dextHeight` 70 mm → 75 mm. `Package m_dintHeight` unchanged at 65.11 mm.

**AX-B** (`GC_AX_B_sep_tail_zero.tbm`)
Single change: `m_dSepTailLength_mm` 85 mm → 0 mm.

**AX-C** (`GC_AX_C_sep_feed_zero.tbm`)
Single change: `m_dSepFeedLength_mm` 10 mm → 0 mm.

**AX-D** (`GC_AX_D_end_overlap_probe.tbm`)
Single change: `m_dElectrodeOverlapAtEnd_mm` 40 mm → 80 mm.

### CENTRAL family

**CEN-A** (`GC_CEN_A_mandrel_probe.tbm`)
Single change: `m_dMandrelThickness_mm` 6.0 mm → 0.5 mm.

---

## TBM file checksums

| Case | Filename | SHA-256 |
|---|---|---|
| T06 baseline (reference, unchanged) | T06_TARGET_AXIAL_SURPLUS_2p00.tbm | `433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71` |
| RAD-A | GC_RAD_A_can_id_probe.tbm | `05db85fc8c27856044d16429dfa7b659656fd250bd190106e0cfb6911ad8deaa` |
| RAD-B | GC_RAD_B_can_rep_xy_probe.tbm | `c15d05f90bfacacb7a7397fa9ecb1b20cec0c856ff23c0f66fe00900ba43d82b` |
| RAD-C | GC_RAD_C_jr_od_probe.tbm | `c82653dcae49e3b33eabb81cd4c6a9387794c42470a79e35b1014487033e2de5` |
| AX-A | GC_AX_A_ext_height_probe.tbm | `379ae8a9d45b2613fe89f039316d8dc46b8fc5f2393cc77f46c445412b823ff5` |
| AX-B | GC_AX_B_sep_tail_zero.tbm | `b535e1cd9603b9400516a93ba39addffa21e8e0822bfd58c3030d4084554f203` |
| AX-C | GC_AX_C_sep_feed_zero.tbm | `32143c9579f08b3f26db4c3cd445a80d5787702cfc69bddf9ee947df7eb99f08` |
| AX-D | GC_AX_D_end_overlap_probe.tbm | `a6e9ed1a8f0e24b752c911a9be3f9536250bd486ece00adcb1f84ffa61cdfd3e` |
| CEN-A | GC_CEN_A_mandrel_probe.tbm | `81a7d8909e85f16b901bffad2024459cbb600980f69ef1d16db849c0bd5da105` |

Verify each file with `sha256sum` or equivalent before starting.

---

## What NOT to do

- Do NOT import any of these TBMs into STAR-CCM+.
- Do NOT measure dimensions from the STEP files.
- Do NOT open or modify the S0 package (ROBERT_STAR_S0_QUALIFICATION).
- Do NOT attach .sim files.
- Do NOT attempt to fix a BDS generation error — just report it.

---

**Status: NOT YET DISPATCHED TO ROBERT**
