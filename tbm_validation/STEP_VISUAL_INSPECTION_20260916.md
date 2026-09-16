# STEP visual inspection — 2026-09-16 client return

Source: `client-data/20260916-tbm-root-surrogate-v2`,
`in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip`.
Render package: `tbm_validation/step_visualization/` (see `README.md` there
for full method/camera/color/tessellation documentation).

This document reports what the renders show. It keeps three things
explicitly separate, as instructed:

- **Measured CAD evidence** — exact numbers from B-Rep bounding boxes on the
  untessellated STEP solids (not from pixels).
- **Visual observation** — what is visible by eye in the rendered images.
- **Interpretation** — a possible reading of the above. Kept minimal here;
  new Siemens/BDS rules are not inferred from appearance alone.

For the runtime-result classification (pass/fail per case, surplus values,
etc.) see the authoritative `NEXTSESSION` and
`tbm_validation/CLIENT_RETURN_ANALYSIS_20260916.md` on this branch — this
document does not repeat or re-derive that analysis.

## Case table

All 17 cases import with **body count = 13** and **identical body names**
(verified by diff across all 17 `_import_log.txt` files):
`Mandrel, Jellyroll, Can, +Ve Tab Root, +Ve Tab Stem, -Ve Tab Root,
-Ve Tab Stem, +Ve Washer, -Ve Washer, +Ve EndPlate, -Ve EndPlate,
+Ve Internal-Post, -Ve Internal-Post`. All 17 show the same
`*** ERR StepReaderData : Unresolved Reference : Fails Count : 1 ***`
reader warning (benign, see README.md).

| Case | STEP filename | Bodies | Render status | Visual observation |
|---|---|---|---|---|
| H01 | H01_POS_ZERO_SURPLUS.step | 13 | OK (A/B/C) | Standard cell topology; +Ve tab-root/stem shortest of the H-series positive-surplus family. |
| H02 | H02_POS_SURPLUS_0p10.step | 13 | OK (A/B/C) | Visually near-indistinguishable from H01 at whole-cell scale (surplus 0.10 mm is sub-pixel at this render size). |
| H03 | H03_POS_SURPLUS_0p70.step | 13 | OK (A/B/C) | +Ve tab-root/stem visibly slightly longer than H01/H02. |
| H04 | H04_POS_SURPLUS_2p00.step | 13 | OK (A/B/C) | +Ve tab-root/stem visibly longer again; largest positive-surplus H-series case. |
| H05 | H05_NEG_ZERO_SURPLUS.step | 13 | OK (A/B/C) | Standard cell topology; -Ve tab mirrors H01's +Ve baseline geometry. |
| H06 | H06_NEG_SURPLUS_0p10.step | 13 | OK (A/B/C) | Near-indistinguishable from H05 at whole-cell scale. |
| H07 | H07_NEG_SURPLUS_0p70.step | 13 | OK (A/B/C) | -Ve tab-root/stem visibly slightly longer than H05/H06. |
| H08 | H08_NEG_SURPLUS_2p00.step | 13 | OK (A/B/C) | -Ve tab-root/stem visibly longer again; largest negative-surplus H-series case. |
| H11 | H11_BOTH_SURPLUS_0p70.step | 13 | OK (A/B/C) | Both +Ve and -Ve tab structures elongated together, symmetric about mid-cell compared to H03/H07. |
| H12 | H12_BOTH_SURPLUS_2p00.step | 13 | OK (A/B/C) | Both tab structures elongated further, symmetric; largest "both surplus" H-series case. |
| H13 | H13_BOTH_TAB_LENGTH_60.step | 13 | OK (A/B/C) | Distinctly longer overall cell (absolute 60 mm tab length spec) vs other H-series cases; both tab structures visibly the longest of the H-series set. |
| T01 | T01_TARGET_AXIAL_TABS65.step | 13 | OK (A/B/C/D) | Target-axial-stack topology, same 13-body structure as H-series; +Ve tab-root/stem shortest of the T-progression. |
| T04 | T04_TARGET_AXIAL_SURPLUS_0p70.step | 13 | OK (A/B/C/D) | +Ve tab-root/stem visibly longer than T01 in fixed-scale end-zoom (view D). |
| T05 | T05_TARGET_AXIAL_SURPLUS_1p00.step | 13 | OK (A/B/C/D) | +Ve tab-root/stem visibly longer again than T04 in view D. |
| T06 | T06_TARGET_AXIAL_SURPLUS_2p00.step | 13 | OK (A/B/C/D) | +Ve tab-root/stem visibly longer than T05 in view D. |
| T07 | T07_TARGET_AXIAL_SURPLUS_5p00.step | 13 | OK (A/B/C/D) | In the fixed-scale view D, +Ve tab-root/stem end position is visually indistinguishable from T06 despite the input surplus target increasing from 2.00 to 5.00 mm. |
| T08 | T08_TARGET_AXIAL_WORKING_DERIVED_HEIGHTS.step | 13 | OK (A/B/C/D) | In view D, +Ve tab-root/stem end position is visually indistinguishable from T06/T07. |

**Render status summary:** 17/17 STEP files found, 17/17 successfully
loaded and rendered. No STEP file failed to import. No body-count or
topology discrepancy across the set.

## T01→T08 progression: measured evidence + visual check (item 9)

**Measured CAD evidence** (exact B-Rep bounding-box top-Y of `+Ve Tab Stem`,
independently computed on the untessellated STEP solids, global axial
coordinate, mm):

| Case | +Ve Tab Stem top-Y (mm) | Δ from T01 (mm) |
|---|---|---|
| T01 | 65.557 | — |
| T04 | 65.812 | +0.255 |
| T05 | 66.112 | +0.555 |
| T06 | 66.275 | +0.718 |
| T07 | 66.275 | +0.718 |
| T08 | 66.275 | +0.718 |

This is an exact numeric match to three cases (T06, T07, T08) sharing an
identical bounding-box top-Y to the last digit recorded, while T01→T04→T05→T06
each increase monotonically.

**Visual observation:** the dedicated fixed-scale, fixed-camera, fixed-crop
comparison image
(`tbm_validation/step_visualization/output/T_PROGRESSION_T01_T04_T05_T06_T07_T08.png`,
built from the six `*_D_POS_END_ZOOM_FIXED_SCALE.png` renders, all sharing
one frozen camera/parallel-scale/crop so no auto-fit normalization can hide
a real size difference) shows the same pattern by eye: the +Ve tab-root/stem
assembly visibly grows from T01 through T06, then the T06/T07/T08 panels are
visually indistinguishable from each other.

**Interpretation (kept separate, minimal):** the measured bounding box and
the fixed-scale visual render agree with each other on the same underlying
fact — whatever geometric quantity controls `+Ve Tab Stem` extent stops
changing once its target-axial surplus setting reaches T06's value (2.00 mm),
even though T07 (5.00 mm) and T08 (working-derived heights) specify larger
inputs. This is reported as an observed geometric fact about the returned
solids, not as an inferred Siemens/BDS rule about why it saturates — the
reason belongs in the runtime-result analysis, not this visual package.

## Files referenced

- `tbm_validation/step_visualization/output/MONTAGE_FULL_TRANSPARENT_ISO.png`
- `tbm_validation/step_visualization/output/MONTAGE_CAN_TRANSPARENT_ISO.png`
- `tbm_validation/step_visualization/output/MONTAGE_INTERNALS_ISO.png`
- `tbm_validation/step_visualization/output/T_PROGRESSION_T01_T04_T05_T06_T07_T08.png` (primary evidence for the saturation observation above)
- `tbm_validation/step_visualization/output/T_PROGRESSION_WHOLECELL_AUTOFIT.png` (whole-cell context only, per-case auto-fit, NOT same scale — do not use for dimensional comparison)
- Per-case: `output/<case>_A_FULL_TRANSPARENT_ISO.png`, `_B_CAN_TRANSPARENT_ISO.png`, `_C_INTERNALS_ISO.png`, `_import_log.txt`
- T-series only: `output/<case>_D_POS_END_ZOOM_FIXED_SCALE.png`
