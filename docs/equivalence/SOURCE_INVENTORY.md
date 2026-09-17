# Source Inventory — OpenFOAM/BDS Thermal Equivalence Audit

**Date:** 2026-09-17
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Purpose:** Enumerate every repository source consulted to reconstruct the OpenFOAM–ECM reference thermal operator and to audit the BDS/T06 geometry against it. See `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md` for the governing requirement.

## Governing/context documents (read this run)

| File | Establishes | Status |
|---|---|---|
| `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md` | Governing objective: reproduce OF reference behaviour, not realistic clearances; JR OD = Can ID = 20.6274 mm, ideal contact by default | Authoritative |
| `NEXTSESSION` | Session state as of 2026-09-10; confirms JR OD target, protected parameters, pending client items | Authoritative (dated) |
| `STARCCM_TBM_PROJECT_CONTEXT.md` | General STAR/TBM project background | Authoritative (dated, not re-read line by line this run beyond context already in memory) |
| `tbm_validation/STAR_IMPORT_SELECTION_ELECTRICAL_BEHAVIOR_NOTE_20260910.md` | STAR battery-cell import requires Core/±Tab parts; minimal electrical topology = JR/core + both tab paths + can/cap | Authoritative |
| `tbm_validation/step_visualization_PREVIEW/STEP_VISUAL_INSPECTION_20260916.md` | T06 body count = 13, named bodies list, T-series axial surplus saturates at T06 | Authoritative, but **not at the path named in the task prompt** (`tbm_validation/STEP_VISUAL_INSPECTION_20260916.md` does not exist; the real file lives at `tbm_validation/step_visualization_PREVIEW/STEP_VISUAL_INSPECTION_20260916.md`) |

### Files named in the task prompt that do NOT exist in this repository

Searched the full repository tree (excluding `.conda*`) for both filenames; neither exists anywhere:

- `tbm_validation/CLIENT_RETURN_ANALYSIS_20260916.md` — **NOT FOUND**
- `tbm_validation/THREE_REGION_DISTRIBUTED_RCR_FEASIBILITY_20260916.md` — **NOT FOUND**

Per instructions, this is documented rather than guessed or fabricated. Any conclusion in this report that would have depended on those two documents is instead drawn directly from the OpenFOAM case files and the BDS STEP geometry.

## OpenFOAM reference-model files (discovered, not assumed)

| File/dir | Establishes | Status |
|---|---|---|
| `cases/wedge_2170/constant/regionProperties` | 3 solid regions: `jellyRoll_rotated`, `shell_rotated` (=Can), `cap_rotated` (=Cap) | Authoritative |
| `cases/wedge_2170/constant/{region}/thermophysicalProperties` (×3) | rho, Cp (tabulated for JR, constant for Can/Cap), full anisotropic kappa tensor per region | Authoritative |
| `cases/wedge_2170/constant/{region}/polyMesh/points` (×3, ASCII) | Exact region bounding boxes → JR radius/height, Can/Cap radii and axial extents (used instead of narrative values) | Authoritative, derived by direct computation this run |
| `cases/wedge_2170/0/{region}/T` (×3) | All boundary condition types: region-coupled interfaces (`turbulentTemperatureRadCoupledMixed`), external convective walls (`externalWallHeatFluxTemperature`, h=160 W/m²K, Ta=298.15K), one interface with explicit `thicknessLayers`/`kappaLayers` contact resistance | Authoritative |
| `cases/wedge_2170/system/jellyRoll_rotated/fvOptions` | Heat source mechanism: `ecmHeatSource` (custom fvOption, `libecmFvOptions.so`), applied only in `jellyRoll_rotated`, `selectionMode all`, deposits into field `h` via `ecmQdot` | Authoritative |
| `cases/wedge_2170/system/controlDict` | ECM coupling function object (`ecmCoupler`): lumped coupling, single zone = whole JR region, external Python process, CSV-driven current profile | Authoritative |
| `cases/wedge_2170/constant/electrical_inputs_from_validation.csv` | Time/current(A) profile driving the ECM coupling (2396 rows, t=0 to 347s) | Authoritative |
| `cases/wedge_2170/postProcessing/jellyRoll_rotated/jellyRollMeanT/` | Existing volume-averaged JR temperature history | **Uncertain** — see below |
| `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` | Narrative restatement of geometry/material constants | Derived/secondary; cross-checked against the actual OpenFOAM files (matches for rho/Cp/k; **does not match** for the heat-source split fractions f_jroll/f_cap/f_can — see below |
| `cases/wedge_2170_constant_heat_rtherm/` | Alternate case: same geometry/materials, constant volumetric heat source (150000 W/m³ in JR, via `scalarSemiImplicitSource`) instead of ECM coupling, and a **different, larger** base-contact resistance (`thicknessLayers=1.804785e-3` m vs `6.015e-7` m in the production case) | Secondary/legacy sensitivity variant, not the primary reference |

### Discrepancies found and left unresolved (not invented away)

1. **Heat-source split.** `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` documents `f_jroll=0.966, f_cap=0.034, f_can=0`. The actual `fvOptions` wiring in `cases/wedge_2170` only exists under `jellyRoll_rotated` — there is no `fvOptions` file under `shell_rotated` or `cap_rotated`. The executable reference model therefore deposits 100% of ECM heat in JellyRoll, 0% in Can, 0% in Cap. This conflicts with the documented fractions. Recorded as an open item in `data/equivalence/openfoam_thermal_operator.json`.
2. **Base-contact resistance value.** `Rtherm_jroll_base = 5.40067678 K/W` is documented, but a first-principles check of the production case's `thicknessLayers=6.01519461276695e-07 m` / `kappaLayers=1` on the JR↔Can "bottom" patch (R ≈ thickness/(kappa·A_full360) ≈ 1.8×10⁻³ K/W) does not reconcile with 5.4 K/W. The `_constant_heat_rtherm` variant's `thicknessLayers=1.804785e-3 m` is closer in order of magnitude to that same back-of-envelope check but still not an exact match. Not resolved; flagged for client/derivation confirmation.
3. **Stale postProcessing data.** `cases/wedge_2170/postProcessing/jellyRoll_rotated/jellyRollMeanT/500/volFieldValue.dat` and the equivalent file under `cases/wedge_2170_constant_heat_rtherm/` are byte-identical, despite the two cases having different heat-source and contact-resistance configurations. At least one is stale/copied. Neither is used as validated transient evidence in this report (see `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md` Phase 6).

## BDS/STAR geometry files (discovered, not assumed)

| File | Establishes | Status |
|---|---|---|
| `in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip` → `T06_TARGET_AXIAL_SURPLUS_2p00.step` | The known-good returned T06 STEP geometry (13 named solids), used directly, not regenerated | Authoritative, client-returned |
| STEP `PRODUCT` records (read via `OCC.Extend.DataExchange.read_step_file_with_names_colors`) | Authoritative per-solid names: `Mandrel, Jellyroll, Can, +Ve/-Ve {Tab Root, Tab Stem, Washer, EndPlate, Internal-Post}` | Authoritative, extracted directly from the STEP file this run (not assumed from the visual-inspection doc) |

## Tooling produced this run

- `tools/audit_bds_openfoam_overlap.py` — reusable, deterministic exact-B-Rep (pythonOCC/OpenCASCADE) overlap tool. Given any BDS STEP file, computes each named solid's exact volumetric intersection with the three OpenFOAM reference domains (derived from `cases/wedge_2170` mesh bounding boxes, not hand-typed numbers) and a pairwise min-distance contact graph. Outputs `artifacts/equivalence/T06_BDS_TO_OPENFOAM_OVERLAP.csv` and `artifacts/equivalence/T06_CONTACT_GRAPH.csv`.
