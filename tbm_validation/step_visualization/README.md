# STEP visual inspection package — 2026-09-16 client return

Visualization-only package for the STEP files returned by the client on
2026-09-16 (`client-data/20260916-tbm-root-surrogate-v2`,
`in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip`).

**Purpose:** let a human visually inspect exactly what STAR-CCM+ / Battery
Design Studio generated for each successfully-imported test case. This is
not a geometry-generation or geometry-repair step. No STEP file is modified,
healed, simplified, remeshed, or reinterpreted anywhere in this pipeline.

## Source STEP files

17 STEP files were returned (all corresponding to `Success` rows in the
client's `hp2170NCA_STAR_TBM_runtime_results_20260914.xlsx`). The `F` series
and the E004-root-failure cases (`H09`, `H10`, `T02`, `T03`, `T09`) did not
produce STEP exports and are not part of this package.

| Case | STEP filename |
|---|---|
| H01 | H01_POS_ZERO_SURPLUS.step |
| H02 | H02_POS_SURPLUS_0p10.step |
| H03 | H03_POS_SURPLUS_0p70.step |
| H04 | H04_POS_SURPLUS_2p00.step |
| H05 | H05_NEG_ZERO_SURPLUS.step |
| H06 | H06_NEG_SURPLUS_0p10.step |
| H07 | H07_NEG_SURPLUS_0p70.step |
| H08 | H08_NEG_SURPLUS_2p00.step |
| H11 | H11_BOTH_SURPLUS_0p70.step |
| H12 | H12_BOTH_SURPLUS_2p00.step |
| H13 | H13_BOTH_TAB_LENGTH_60.step |
| T01 | T01_TARGET_AXIAL_TABS65.step |
| T04 | T04_TARGET_AXIAL_SURPLUS_0p70.step |
| T05 | T05_TARGET_AXIAL_SURPLUS_1p00.step |
| T06 | T06_TARGET_AXIAL_SURPLUS_2p00.step |
| T07 | T07_TARGET_AXIAL_SURPLUS_5p00.step |
| T08 | T08_TARGET_AXIAL_WORKING_DERIVED_HEIGHTS.step |

Working copies of the STEP files used to run this pipeline were extracted
from the raw client package into a scratch directory; the raw package itself
lives untouched on `client-data/20260916-tbm-root-surrogate-v2` and was not
modified by this work.

## Method / tools

- **STEP import**: `pythonocc-core` 7.9.0 (OpenCASCADE Technology 7.9
  Python bindings), via `OCC.Extend.DataExchange.read_step_file_with_names_colors`,
  which internally uses `STEPCAFControl_Reader` (OCAF/XCAF) so body names are
  recovered exactly as authored in the STEP file (e.g. `Cylindrical Cell: Can`).
  This is a direct, lossless read of the STEP B-Rep geometry — no conversion,
  healing, or simplification is applied to the solids themselves.
- **Tessellation (visualization only)**: `BRepMesh_IncrementalMesh` with
  linear deflection 0.02 mm, angular deflection 0.3 rad. This produces a
  triangulated surface **only for on-screen rendering**. It is never written
  back over the STEP file, never fed into any CAD-generation step, and is
  not used for any dimensional conclusion in this package — all measured
  dimensions quoted in `STEP_VISUAL_INSPECTION_20260916.md` come from exact
  B-Rep bounding boxes (`Bnd_Box`/`BRepBndLib`) on the untessellated shapes,
  not from the triangulated mesh.
- **Rendering**: `pyvista` 0.48.4 (VTK), off-screen, software rasterization
  via OSMesa (`LD_PRELOAD=.../libOSMesa.so`, no GPU/X11 required).
- **Montage/contact-sheet compositing**: Pillow (PIL), pure 2D image
  compositing of the already-rendered PNGs — no geometry involved.

## Camera

All 17 cases share the same **global cylindrical axis: Y** (confirmed by
inspecting the overall bounding box of every returned STEP: Y-extent is
~65–70 mm, X/Z-extent is ~21 mm in every case).

- **Projection**: orthographic (parallel projection enabled).
- **View direction**: `(1,1,1)` normalized diagonal (classic isometric).
- **View-up vector**: `(0,1,0)` — the axial direction, so the cell reads as
  vertical in every image.
- **Per-case renders (A/B/C, see below)**: the camera auto-fits to each
  case's own bounding box (`reset_camera`) so the complete cell fills the
  frame. This means the *orientation* is identical across cases but the
  *zoom/scale* is not — appropriate for "does this look like a battery
  cell" inspection, but **not** appropriate for comparing small absolute
  dimensional changes between cases.
- **Fixed-scale end-zoom render (D, T-series only)**: same orientation, but
  the camera position/focal point/parallel scale are frozen to one shared
  value (`FIXED_BOUNDS` in `render_end_zoom_fixed_scale.py`) for every case
  in the comparison. This is the correct view for judging whether generated
  tab-root/tab-stem geometry actually changes size between cases, since nothing
  in the camera setup can visually compensate for a real size difference.

## Transparency settings

| View | Can opacity | Everything else |
|---|---|---|
| `A_FULL_TRANSPARENT_ISO` | 0.45 | 0.45 (uniform, moderate) |
| `B_CAN_TRANSPARENT_ISO` | 0.08 | 0.92 |
| `C_INTERNALS_ISO` | 0.0 (hidden) | 1.0 (opaque) |
| `D_POS_END_ZOOM_FIXED_SCALE` (T-series only) | 0.10 | Jellyroll 0.35, else 0.95 |
| `E_THREEPART_CAN_TRANSPARENT_ISO` | 0.10 | 0.92 (Jellyroll + Cap only) |
| `F_THREEPART_INTERNALS_ISO` | 0.0 (hidden) | 1.0 (Jellyroll + Cap only) |

## Three-part reduced view (Can + Jellyroll + Cap only)

Added on request to compare the returned BDS/STAR-CCM+ topology against the
target ECM-OpenFOAM coupling topology, which represents a cell with only
three parts. `render_three_part.py` selects **only** the bodies `Can`,
`Jellyroll`, `+Ve EndPlate`, `-Ve EndPlate` from each already-loaded STEP
file and renders those alone — every other body (Mandrel, both tab-roots,
both tab-stems, both washers, both internal-posts) is simply not drawn.
This is a body-selection filter for rendering purposes only; it does not
merge, heal, or modify any solid, and the untouched 13-body STEP file is
unaffected.

**Naming mapping (explicit, not inferred from appearance):** the returned
STEP files have no body literally named "Cap". The closest structural
equivalent — the axial end structure that closes off the can — is the
`EndPlate` body (`+Ve EndPlate` / `-Ve EndPlate`). This script and the
`STEP_VISUAL_INSPECTION_20260916.md` three-part section treat
**Cap := EndPlate**. This is a naming/selection choice made for this
comparison, not a measured or vendor-confirmed fact, and it is stated here
so it isn't mistaken for one. All 17 cases were confirmed to contain
exactly these 4 bodies (Can, Jellyroll, +Ve EndPlate, -Ve EndPlate) with no
`render_three_part.py` warning of a missing/extra body.

Bounding box / camera fit for these views is computed from the 3-part
subset only (Can+Jellyroll+Cap), not the full 13-body cell, so the
framing is tighter and centered on just those parts.

Outputs: `<case>_E_THREEPART_CAN_TRANSPARENT_ISO.png`,
`<case>_F_THREEPART_INTERNALS_ISO.png`,
`MONTAGE_THREEPART_CAN_TRANSPARENT_ISO.png`,
`MONTAGE_THREEPART_INTERNALS_ISO.png`.

## Body-name to color mapping

Colors are fixed per canonical body name and identical across every case and
every view. They are chosen purely for visual distinguishability and do
**not** imply any known material (per task instructions, no material is
assumed).

| Body (short name from STEP) | Color (RGB 0–1) | Conceptual group |
|---|---|---|
| Can | (0.80, 0.80, 0.80) light gray | Can |
| Jellyroll | (0.85, 0.66, 0.13) gold | Jellyroll |
| Mandrel | (0.30, 0.30, 0.34) dark slate | Mandrel |
| +Ve Tab Root | (0.80, 0.10, 0.10) red | Positive-side structures |
| +Ve Tab Stem | (0.92, 0.40, 0.10) orange-red | Positive-side structures |
| +Ve Washer | (0.60, 0.00, 0.00) dark red | Positive-side structures |
| +Ve EndPlate | (0.92, 0.55, 0.45) salmon | Positive-side structures |
| +Ve Internal-Post | (0.55, 0.10, 0.20) maroon | Positive-side structures |
| -Ve Tab Root | (0.10, 0.20, 0.85) blue | Negative-side structures |
| -Ve Tab Stem | (0.10, 0.55, 0.92) teal-blue | Negative-side structures |
| -Ve Washer | (0.00, 0.00, 0.55) navy | Negative-side structures |
| -Ve EndPlate | (0.45, 0.65, 0.92) sky blue | Negative-side structures |
| -Ve Internal-Post | (0.28, 0.10, 0.55) indigo | Negative-side structures |

Exact mapping/source code: `step_render_common.py` (`BODY_COLORS`, `group_of`).

## STEP import warnings

Every one of the 17 returned STEP files produces the identical single
warning from the OCCT STEP reader, written directly to process stdout by
the native (C++) reader code:

```
*** ERR StepReaderData : Unresolved Reference : Fails Count : 1 ***
```

This was captured at the OS file-descriptor level (Python's
`contextlib.redirect_stdout` does not intercept native C++ stdout writes;
an earlier attempt at Python-level capture silently missed this line — see
git history of `render_case.py`/`step_render_common.py` for that
correction). The warning is identical in every file and does not visibly
affect the recovered body count (13/13 in all cases) or geometry, but it is
recorded verbatim per case in `output/<case>_import_log.txt` for the record.
No further interpretation of this warning is offered here.

## Files

```
tbm_validation/step_visualization/
  README.md                          -- this file
  step_render_common.py              -- shared STEP loading / tessellation / color-mapping helpers
  render_case.py                     -- renders A/B/C views for one case
  render_end_zoom_fixed_scale.py     -- renders fixed-scale D view for T-series comparison
  make_montages.py                   -- builds contact-sheet montages from rendered PNGs
  output/
    <case>_A_FULL_TRANSPARENT_ISO.png
    <case>_B_CAN_TRANSPARENT_ISO.png
    <case>_C_INTERNALS_ISO.png
    <case>_import_log.txt            -- body list + STEP reader stdout, per case
    T01..T08_D_POS_END_ZOOM_FIXED_SCALE.png
    MONTAGE_FULL_TRANSPARENT_ISO.png
    MONTAGE_CAN_TRANSPARENT_ISO.png
    MONTAGE_INTERNALS_ISO.png
    T_PROGRESSION_T01_T04_T05_T06_T07_T08.png       -- fixed-scale end-zoom comparison (primary evidence)
    T_PROGRESSION_WHOLECELL_AUTOFIT.png             -- whole-cell context only, NOT same scale
```

## Reproducing

```bash
export LD_PRELOAD=/workspace/.conda/envs/pv/lib/libOSMesa.so   # headless OSMesa rendering
cd tbm_validation/step_visualization
python3 render_case.py <CASE_ID> <path-to-step> ./output
python3 render_end_zoom_fixed_scale.py ./output <dir-containing-T-series-steps>
python3 make_montages.py ./output
```
