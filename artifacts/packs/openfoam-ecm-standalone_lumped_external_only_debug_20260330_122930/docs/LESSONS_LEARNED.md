# Lessons Learned (chtBlockMeshCube_ecm)

## Mesh and Run Workflow
- `transformPoints -allRegions` is overwritten if `Allrun.pre` runs `blockMesh`.
  Use one of: edit `system/blockMeshDict`, or skip mesh regeneration after initial build.
- For multi-region cases, `topoSet` should define `cellZoneSet` entries directly,
  then `splitMeshRegions -cellZones -overwrite` (tutorial pattern).
- After splitting, use `restore0Dir` and `changeDictionary -region <name>` to apply
  region-specific BCs; avoid stale or default BCs.

## Energy Source Sign
- In `chtMultiRegionFoam` assembled energy solve, `ecmQdot` must be applied with a
  minus sign in `fvOptions` to yield heating (i.e., `eqn.source() -= ecmQdot*V`).
- Verify sign with a 1-step unit test and compare measured dT to
  `dT = Q*dt/(rho*Cp*V)`.

## Solver Configuration
- Match `fvSchemes`/`fvSolution` to the simplest applicable tutorial. Missing entries
  (e.g., `div(((rho*nuEff)*dev2(T(grad(U)))))`, `fluxRequired p_rgh`) cause failures.
- In `chtMultiRegionFoam` the fluid `PIMPLE` dict must define a pressure reference
  (either `pRefCell` or `pRefPoint` + `pRefValue`) even when running with `frozenFlow yes`.

## FunctionObject Write Controls (Extra Time Folders)
- Even if `controlDict.writeControl` is `runTime`, a `functionObject` can still
  write its own outputs every timestep via its own default `writeControl`.
- Symptom: unexpected extra time directories containing only `ecmQdot` (or other
  functionObject-written fields), while other fields follow `writeTime`.
- Fix: set the functionObject write control explicitly, e.g. in `controlDict`:
  `ecmCoupling.writeControl writeTime;` so it only writes when the solver writes.

## Sanity Checks
- Confirm selected cellZone count and volume in logs (e.g., 1000 cells, V=0.001).
- Confirm `Q_sum_check` and `volIntegrate(ecmQdot)` match the intended power.
- Expect small temperature changes for large thermal mass; increase Q or duration
  for visible changes.

## Logging and Hygiene
- Clean stale region/system artifacts created by earlier split runs.
- Track all setup deviations and verification outputs in logs.

## Validation Harness Safeguards
- Treat shared runner code as part of the validated system. A helper like
  `_run()` can change physics outcomes if it modifies the execution environment.
- When a harness result looks wrong, rerun the exact generated case directly
  from the shell before changing model or solver code.
- If direct-run and harness-run disagree, stop and debug the launch path first:
  - sourced bashrc files
  - overridden `FOAM_*` variables
  - overridden `PATH` / `LD_LIBRARY_PATH`
- For generated validation cases, clean runtime carryover explicitly:
  - `ecm_state.json`
  - `ecm_last_good.bin`
  - `artifacts/runtime/`
  - stale time directories
- Do not assume “same case files” means “same run.” Execution path and runtime
  state must also match.
- Add a standard equivalence check for harnessed validations:
  - same generated case
  - direct shell run
  - harness run
  - compare key metrics before escalating to solver or model debugging

## Region Renames and ParaView
- When renaming regions (e.g., core -> jellyRoll), remove old region folders under
  `constant/` and any cached `foam.foam` entries. ParaView enumerates regions from
  on-disk folders, so stale directories can appear as phantom regions and hide the
  real mesh in the GUI.

## PostProcessing Staleness
- PostProcessing outputs (e.g., `postProcessing/volFieldValue`, `postProcessing/samplePlanes`)
  are not auto-invalidated when you rerun a case. If you generate reports after a
  rerun without clearing these directories, you can end up plotting stale data that
  does not match the current fields on disk.
- Fix: delete `postProcessing/` before regenerating plots/reports, and validate the
  report against a direct field check (e.g., `postProcess -func fieldMinMax(T)` at
  the target time and region). This catches mismatches early.
