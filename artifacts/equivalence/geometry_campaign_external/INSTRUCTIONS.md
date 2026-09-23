# TBM Geometry Export Request

**Date:** 2026-09-23
**Package:** TBM_GEOMETRY_EXPORT_REQUEST_20260923

---

## Purpose

Eight TBM files are supplied. For each file:

1. Open the TBM in Battery Design Studio (BDS).
2. Let BDS recompute/generate the cell geometry completely.
3. **If generation succeeds:** export the geometry as a STEP file. Name the exported file using the same base name as the TBM (e.g. `GC_RAD_A_can_id_probe.step`). Return all STEP files.
4. **If generation fails:** record the exact error text shown by BDS (and optionally a screenshot). Return the error text. Do not attempt to fix the error.

No manual geometry measurements are required. No STAR simulation setup or `.sim` files are required. The returned STEP files will be analysed on our side.

---

## Case list

The following eight TBM files are included in the `input/` folder:

| # | Filename |
|---|---|
| 1 | GC_RAD_A_can_id_probe.tbm |
| 2 | GC_RAD_B_can_rep_xy_probe.tbm |
| 3 | GC_RAD_C_jr_od_probe.tbm |
| 4 | GC_AX_A_ext_height_probe.tbm |
| 5 | GC_AX_B_sep_tail_zero.tbm |
| 6 | GC_AX_C_sep_feed_zero.tbm |
| 7 | GC_AX_D_end_overlap_probe.tbm |
| 8 | GC_CEN_A_mandrel_probe.tbm |

Please verify each file is present before starting.

---

## File checksums

Verify the delivered TBM files against these SHA-256 values before use:

| Filename | SHA-256 |
|---|---|
| GC_RAD_A_can_id_probe.tbm | `05db85fc8c27856044d16429dfa7b659656fd250bd190106e0cfb6911ad8deaa` |
| GC_RAD_B_can_rep_xy_probe.tbm | `c15d05f90bfacacb7a7397fa9ecb1b20cec0c856ff23c0f66fe00900ba43d82b` |
| GC_RAD_C_jr_od_probe.tbm | `c82653dcae49e3b33eabb81cd4c6a9387794c42470a79e35b1014487033e2de5` |
| GC_AX_A_ext_height_probe.tbm | `379ae8a9d45b2613fe89f039316d8dc46b8fc5f2393cc77f46c445412b823ff5` |
| GC_AX_B_sep_tail_zero.tbm | `b535e1cd9603b9400516a93ba39addffa21e8e0822bfd58c3030d4084554f203` |
| GC_AX_C_sep_feed_zero.tbm | `32143c9579f08b3f26db4c3cd445a80d5787702cfc69bddf9ee947df7eb99f08` |
| GC_AX_D_end_overlap_probe.tbm | `a6e9ed1a8f0e24b752c911a9be3f9536250bd486ece00adcb1f84ffa61cdfd3e` |
| GC_CEN_A_mandrel_probe.tbm | `81a7d8909e85f16b901bffad2024459cbb600980f69ef1d16db849c0bd5da105` |

Verify with `sha256sum` or equivalent before starting.
