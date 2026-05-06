# STATUS

## Active
- Validating `cases/lumped` CHT setup + coupling stability (transient `chtMultiRegionFoam`, dummy ambient fluid with `frozenFlow`, stable `writeTime` outputs, and correct heat-source sign).
- Running detailed coupling validation: jsonWrapper (chtBlockMeshCube_ecm) and element-wise binary (chtMultiRegionSimpleFoam_cpuCabinet_ecm); wedge_volumeCan_test blocked by missing regionProperties (see artifacts/reports/ecm_coupling_test_report_2026-03-17.pdf).
- Rebuild `cases/lumped` and `cases/lumped_solid` meshes with new 2170 geometry inputs (blockMesh + snappyHexMesh + splitMeshRegions).
- Remove ambient zone from `cases/lumped_solid` snappyHexMesh locationsInMesh and regenerate mesh to keep solids-only regions.
- Lesson learned: do not disable `ecmCoupler` during coupling validation; fix backend dependencies (e.g., `numpy`) and proceed with the intended coupling test.

## Done
- Bootstrap repository operating rules, logs, and registers (MY_CODEX_BEST_PRACTICES_RULES).
- Added chat log rule and `artifacts/logs/chat.log` for per-prompt tracking.
- Removed non-jellyRoll/cap/shell cases under `cases/`.
- Noted OpenFOAM 2D modeling uses single-cell-thick 3D meshes with `empty` front/back patches (assumptions register).
- Fixed CHT solid fvOptions source sign so positive ecmQdot adds heat.
- Added CHT blockMesh cube ECM test case (cases/chtBlockMeshCube_ecm).
- Built `libecmCouplingFunctionObjects.so` via `./Allwmake` (see artifacts/logs/build_Allwmake.log).
- Added ECM output record-count mismatch warning with best-effort mapping.
- Implemented transactional `stepId` IO, adaptive relaxation, `tEffMode`, axial heat profiles, and `Q_sum_check` logging in `ecmCoupler`.
- Added missing-output limit handling with `missingOutputAction` (warn/degraded/fatal).
- Split MY_CODEX_BEST_PRACTICES_RULES into mode-based guides under docs/codex_modes.
- Added STAR-CCM+ migration plan to overall project planning.
- Fixed `libecmCouplingFunctionObjects.so` runtime path and unblocked non-lumped case load in `cases/distributed` (see artifacts/logs/3DcylinricalCellPureCondution_nonlumped_run2.log).
- Stabilized non-lumped run by clamping mock ECM inputs/outputs; rerun holds `Q_sum_check` steady without FPE (see artifacts/logs/3DcylinricalCellPureCondution_nonlumped_run4.log).
- Added detailed STAR-CCM+ migration doc and linked it from the project plan.
- Added TU Berlin validation script in `tools/validation/`.
- Added OpenFOAM best practices doc, governance templates (CONTRIBUTING, LICENSE, CHANGELOG), issue/PR templates, CI workflow, and logging/data management docs.
- Ran `ecm_io` parser smoke test (in-memory).
- Ran `cases/scalarTransport_ecm` in serial and parallel from a temp copy (logs in artifacts/logs/scalarTransport_ecm_serial.log and artifacts/logs/scalarTransport_ecm_parallel.log).
- Ran CHT cases in parallel:
  - `cases/chtMultiRegionSimpleFoam_ecm` (log: artifacts/logs/chtMultiRegionSimpleFoam_ecm_parallel.log).
  - `cases/chtMultiRegionSimpleFoam_cpuCabinet_ecm` (log: artifacts/logs/chtMultiRegionSimpleFoam_cpuCabinet_ecm_parallel.log).
- Added run-passport workflow with metrics definitions, thresholds, and tooling.
- Updated scalarTransport ECM IO/coupler to support v2 headers (stepId).
- Reran scalarTransport_ecm and chtMultiRegionSimpleFoam_ecm with adiabatic boundaries/no flow (logs in artifacts/logs/*_adiabatic_rerun.log).
- Regenerated CHT probe outputs (5 random points) and adiabatic probe plots/CSVs in artifacts/plots.
- Added last-good ECM snapshot persistence (binary file, configurable via `lastGoodFile`) and documented it.
- Generated updated lumped-case PDF report from the stable transient run (artifacts/reports/lumped_ecm_run_report_20260323_205250.pdf) using tools/generate_lumped_report.py.
- Added `jsonWrapper` IO mode for `ecmCoupler` (JSON input/output via `ecm_coupling_wrapper.py`) with auto-reset on stepId<=1; validated on a short CHT run (log: artifacts/logs/chtBlockMeshCube_ecm_jsonwrapper_short_solver_rerun2.log).
- Updated cpuCabinet case-local `ecm_io.py` to accept v2 headers; produced long-timeout coupling report (artifacts/reports/ecm_coupling_test_report_2026-03-17.pdf).
- Added CSV-driven time-dependent `electricalInputs` for `ecmCoupler` and documented usage; rebuild succeeded (CSV run not yet validated).
- Validated CSV-driven electrical inputs on a temp `chtBlockMeshCube_ecm` run; `Q_sum_check` followed the time series and decayed to zero (log: artifacts/logs/chtBlockMeshCube_ecm_csv_inputs2d.log).
- Added validation scripts for Khan and Stanford datasets with usage notes in tools/validation/README.md.
- Set up snappyHexMesh workflow for `cases/lumped` using cellFull.stl; generated core/shell/ambient regions via locationsInMesh and splitMeshRegions (logs in case log.snappyHexMesh, log.splitMeshRegions).
- Re-seeded snappyHexMesh for `cases/lumped` to create core/shell/cap regions; rebuilt mesh with zero illegal faces (logs in case log.snappyHexMesh, log.splitMeshRegions).
- Renamed core -> jellyRoll in `cases/lumped` and rebuilt mesh; splitMeshRegions now shows shell/jellyRoll/cap with clean mesh.
- Added `T` initial/boundary fields for jellyRoll/shell/cap with `externalWall` fixed at 313.15 K and coupled interface BCs.
- Wired `ecmCoupler` into `cases/lumped` (jellyRoll, lumped totalPower, binary I/O, masterGather).
- Added passive ambient region + fixed 40C outer boundary for CHT solver compatibility.
- Generated 0-100 s coupling run report for `cases/lumped` with 5x heat (artifacts/reports/3DcylindricalCellPureConduction_ecm_run_report_20260321_125101.pdf).
- Added mapping-table support (plus synthetic mapping) in `ecm/ecm_coupler.py` for non-lumped ECM/mesh coupling and documented it in `docs/INTEGRATION.md`.
- Reran non-lumped cylinder case with adjusted heat rejection inputs and updated report (artifacts/reports/3DcylinricalCellPureCondution_nonlumped_ecm_run_report_20260321_191253.pdf).
- Built `chtMultiRegionSolidFoam` and ran `cases/lumped_solid` to t=5 (log: artifacts/logs/lumped_run_20260324_154518.log); ECM backend warnings due to missing numpy.
- Installed numpy/pandas and reran `cases/lumped_solid` with coupler active to t=5 (log: artifacts/logs/lumped_run_20260324_155629.log); Q_sum_check steady ~90 W.
- Extended `cases/lumped_solid` to 100 s and reran with coupler active (log: artifacts/logs/lumped_run_20260324_160243.log); generated full report using default template (artifacts/reports/lumped_solid_ecm_run_report_20260324_160501.pdf).
- Updated 2170 geometry inputs: added `cellFull_2170.stl`, scaled locationsInMesh, and adjusted blockMesh domain/cell counts for isotropic 1 mm cells.
- Added rule to prevent running cases with ecmCoupler configured when the coupling library is missing.
- Corrected ecmHeatSource sign in `cases/lumped_solid` and `cases/lumped` after validation (use `-=` on ecmQdot to add heat).

## Blocked
- None.
